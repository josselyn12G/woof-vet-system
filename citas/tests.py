from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Roles
from mascotas.tests import crear_mascota, crear_usuario

from .models import Cita, EstadoCita, HorarioVeterinario, Servicio
from .services import TURNO_OCUPADO, AgendaService


def crear_veterinario(username='sofia', **datos):
    return crear_usuario(username, rol=Roles.VETERINARIO, **datos)


def crear_servicio(**datos):
    valores = {'nombre': 'Consulta general', 'duracion_min': 30, 'precio': Decimal('25.00')}
    valores.update(datos)
    return Servicio.objects.create(**valores)


def crear_horario(veterinario, inicio, fin, fecha=date(2026, 11, 2)):
    return HorarioVeterinario.objects.create(veterinario=veterinario, fecha=fecha, hora_inicio=inicio, hora_fin=fin)


class ServicioModelTests(TestCase):
    def test_str_devuelve_el_nombre(self):
        self.assertEqual(str(crear_servicio()), 'Consulta general')

    def test_un_servicio_nuevo_queda_activo(self):
        self.assertTrue(crear_servicio().activo)

    def test_precio_cero_no_pasa_la_validacion(self):
        servicio = Servicio(nombre='Vacunación', duracion_min=20, precio=Decimal('0'))
        with self.assertRaises(ValidationError) as error:
            servicio.full_clean()
        self.assertIn('precio', error.exception.message_dict)

    def test_duracion_cero_no_pasa_la_validacion(self):
        servicio = Servicio(nombre='Vacunación', duracion_min=0, precio=Decimal('18'))
        with self.assertRaises(ValidationError) as error:
            servicio.full_clean()
        self.assertIn('duracion_min', error.exception.message_dict)

    def test_la_base_rechaza_precio_cero(self):
        # Aunque alguien se salte full_clean(), el CheckConstraint lo impide
        with self.assertRaises(IntegrityError):
            crear_servicio(precio=Decimal('0'))

    def test_la_base_rechaza_duracion_cero(self):
        with self.assertRaises(IntegrityError):
            crear_servicio(duracion_min=0)

    def test_el_nombre_es_unico(self):
        crear_servicio()
        with self.assertRaises(IntegrityError):
            crear_servicio()

    def test_los_veterinarios_quedan_en_el_servicio(self):
        servicio = crear_servicio()
        sofia = crear_veterinario()
        servicio.veterinarios.add(sofia)
        self.assertEqual(list(sofia.servicios.all()), [servicio])

    def test_solo_se_ofrecen_veterinarios(self):
        crear_usuario('ana')  # cliente
        sofia = crear_veterinario()
        formulario = modelform_factory(Servicio, fields=['veterinarios'])()
        self.assertEqual(list(formulario.fields['veterinarios'].queryset), [sofia])


class HorarioVeterinarioModelTests(TestCase):
    def setUp(self):
        self.sofia = crear_veterinario()

    def horario(self, inicio, fin, **datos):
        valores = {'veterinario': self.sofia, 'fecha': date(2026, 11, 2), 'hora_inicio': inicio, 'hora_fin': fin}
        valores.update(datos)
        return HorarioVeterinario(**valores)

    def test_un_bloque_valido_pasa(self):
        self.horario(time(9), time(12)).full_clean()

    def test_fin_antes_del_inicio_no_pasa_la_validacion(self):
        with self.assertRaises(ValidationError) as error:
            self.horario(time(12), time(9)).full_clean()
        self.assertIn('hora_fin', error.exception.message_dict)

    def test_fin_igual_al_inicio_no_pasa_la_validacion(self):
        with self.assertRaises(ValidationError):
            self.horario(time(9), time(9)).full_clean()

    def test_la_base_rechaza_fin_antes_del_inicio(self):
        with self.assertRaises(IntegrityError):
            crear_horario(self.sofia, time(12), time(9))

    def test_bloques_cruzados_no_pasan(self):
        crear_horario(self.sofia, time(9), time(12))
        for inicio, fin in [(time(11), time(13)), (time(8), time(10)), (time(10), time(11)), (time(8), time(13))]:
            with self.subTest(inicio=inicio, fin=fin), self.assertRaises(ValidationError):
                self.horario(inicio, fin).full_clean()

    def test_bloques_seguidos_si_pasan(self):
        crear_horario(self.sofia, time(9), time(12))
        self.horario(time(12), time(14)).full_clean()
        self.horario(time(7), time(9)).full_clean()

    def test_el_mismo_bloque_otro_dia_si_pasa(self):
        crear_horario(self.sofia, time(9), time(12))
        self.horario(time(9), time(12), fecha=date(2026, 11, 3)).full_clean()

    def test_otro_veterinario_puede_tener_el_mismo_bloque(self):
        crear_horario(self.sofia, time(9), time(12))
        self.horario(time(9), time(12), veterinario=crear_veterinario('mateo')).full_clean()

    def test_editar_un_bloque_no_choca_consigo_mismo(self):
        bloque = crear_horario(self.sofia, time(9), time(12))
        bloque.hora_fin = time(13)
        bloque.full_clean()

    def test_un_cliente_no_puede_tener_horario(self):
        with self.assertRaises(ValidationError) as error:
            self.horario(time(9), time(12), veterinario=crear_usuario('ana')).full_clean()
        self.assertIn('veterinario', error.exception.message_dict)


def datos_servicio(**cambios):
    """Datos del formulario de servicio que pasan todas las validaciones."""
    datos = {'nombre': 'Vacunación', 'descripcion': 'Vacunas del calendario', 'duracion_min': '20',
             'precio': '18.00', 'activo': 'on'}
    datos.update(cambios)
    return datos


class CatalogoAccesoTests(TestCase):
    """Solo el administrador entra al catálogo; el cliente y el veterinario reciben 403 (RF-04)."""

    def setUp(self):
        self.servicio = crear_servicio()
        self.paginas = [
            reverse('citas:servicios'),
            reverse('citas:servicio_crear'),
            reverse('citas:servicio_editar', args=[self.servicio.pk]),
            reverse('citas:servicio_eliminar', args=[self.servicio.pk]),
        ]
        self.url_estado = reverse('citas:servicio_estado', args=[self.servicio.pk])

    def test_el_administrador_entra(self):
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        for url in self.paginas:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_cliente_y_veterinario_reciben_403(self):
        for usuario in [crear_usuario('ana'), crear_veterinario()]:
            self.client.force_login(usuario)
            for url in self.paginas:
                with self.subTest(rol=usuario.rol, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(self.url_estado).status_code, 403)
        self.servicio.refresh_from_db()
        self.assertTrue(self.servicio.activo)  # el POST rechazado no cambió nada

    def test_sin_sesion_redirige_al_login(self):
        for url in self.paginas:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('cuentas:login'), respuesta.url)


class CatalogoServiciosTests(TestCase):
    def setUp(self):
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        self.sofia = crear_veterinario(first_name='Sofía', last_name='Paredes')

    def nombres(self, **filtros):
        respuesta = self.client.get(reverse('citas:servicios'), filtros)
        return [servicio.nombre for servicio in respuesta.context['servicios']]

    def test_crear_un_servicio_con_veterinarios(self):
        respuesta = self.client.post(reverse('citas:servicio_crear'), datos_servicio(veterinarios=[self.sofia.pk]))
        self.assertRedirects(respuesta, reverse('citas:servicios'))
        servicio = Servicio.objects.get(nombre='Vacunación')
        self.assertEqual(servicio.precio, Decimal('18.00'))
        self.assertEqual(list(servicio.veterinarios.all()), [self.sofia])

    def test_el_formulario_muestra_casillas_solo_de_veterinarios_activos(self):
        crear_usuario('ana')  # cliente
        crear_veterinario('mateo', is_active=False)
        respuesta = self.client.get(reverse('citas:servicio_crear'))
        self.assertContains(respuesta, f'type="checkbox" name="veterinarios" value="{self.sofia.pk}"')
        self.assertContains(respuesta, 'Sofía Paredes')
        self.assertEqual(list(respuesta.context['form'].fields['veterinarios'].queryset), [self.sofia])

    def test_no_acepta_un_cliente_como_veterinario(self):
        ana = crear_usuario('ana')
        respuesta = self.client.post(reverse('citas:servicio_crear'), datos_servicio(veterinarios=[ana.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('veterinarios', respuesta.context['form'].errors)
        self.assertFalse(Servicio.objects.exists())

    def test_precio_y_duracion_cero_se_rechazan_en_el_servidor(self):
        respuesta = self.client.post(reverse('citas:servicio_crear'), datos_servicio(precio='0', duracion_min='0'))
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context['form'].errors
        self.assertIn('precio', errores)
        self.assertIn('duracion_min', errores)
        self.assertFalse(Servicio.objects.exists())

    def test_precio_negativo_se_rechaza(self):
        respuesta = self.client.post(reverse('citas:servicio_crear'), datos_servicio(precio='-5'))
        self.assertIn('precio', respuesta.context['form'].errors)

    def test_no_repite_el_nombre_aunque_cambien_las_mayusculas(self):
        crear_servicio(nombre='Vacunación')
        respuesta = self.client.post(reverse('citas:servicio_crear'), datos_servicio(nombre='  vacunación '))
        self.assertIn('nombre', respuesta.context['form'].errors)

    def test_editar_un_servicio(self):
        servicio = crear_servicio()
        respuesta = self.client.post(
            reverse('citas:servicio_editar', args=[servicio.pk]),
            datos_servicio(nombre='Consulta general', precio='30.00', veterinarios=[self.sofia.pk]),
        )
        self.assertRedirects(respuesta, reverse('citas:servicios'))
        servicio.refresh_from_db()
        self.assertEqual(servicio.precio, Decimal('30.00'))
        self.assertEqual(list(servicio.veterinarios.all()), [self.sofia])

    def test_el_formulario_de_edicion_muestra_el_precio_sin_coma(self):
        # El input type="number" no entiende "25,00": el valor va con punto
        servicio = crear_servicio()
        respuesta = self.client.get(reverse('citas:servicio_editar', args=[servicio.pk]))
        self.assertContains(respuesta, 'value="25.00"')

    def test_desactivar_y_activar_no_borra_el_servicio(self):
        servicio = crear_servicio()
        url = reverse('citas:servicio_estado', args=[servicio.pk])
        self.assertRedirects(self.client.post(url), reverse('citas:servicios'))
        servicio.refresh_from_db()
        self.assertFalse(servicio.activo)
        self.client.post(url)
        servicio.refresh_from_db()
        self.assertTrue(servicio.activo)

    def test_desactivar_no_funciona_con_get(self):
        servicio = crear_servicio()
        self.assertEqual(self.client.get(reverse('citas:servicio_estado', args=[servicio.pk])).status_code, 405)

    def test_eliminar_un_servicio_sin_citas(self):
        servicio = crear_servicio()
        respuesta = self.client.post(reverse('citas:servicio_eliminar', args=[servicio.pk]))
        self.assertRedirects(respuesta, reverse('citas:servicios'))
        self.assertFalse(Servicio.objects.exists())

    def test_un_servicio_con_citas_no_se_borra(self):
        # Cita.servicio será PROTECT: se simula el error que Django lanza en ese caso
        servicio = crear_servicio()
        with patch.object(Servicio, 'delete', side_effect=ProtectedError('tiene citas', set())):
            respuesta = self.client.post(reverse('citas:servicio_eliminar', args=[servicio.pk]), follow=True)
        self.assertContains(respuesta, 'Desactívalo en su lugar')
        self.assertTrue(Servicio.objects.filter(pk=servicio.pk).exists())

    def test_la_lista_filtra_por_estado_y_busca(self):
        crear_servicio(nombre='Consulta general')
        crear_servicio(nombre='Peluquería', activo=False)
        self.assertEqual(self.nombres(), ['Consulta general', 'Peluquería'])
        self.assertEqual(self.nombres(estado='activos'), ['Consulta general'])
        self.assertEqual(self.nombres(estado='inactivos'), ['Peluquería'])
        self.assertEqual(self.nombres(q='consul'), ['Consulta general'])
        self.assertEqual(self.nombres(estado='inventado'), ['Consulta general', 'Peluquería'])

    def test_la_lista_muestra_precio_y_veterinarios(self):
        crear_servicio().veterinarios.add(self.sofia)
        respuesta = self.client.get(reverse('citas:servicios'))
        self.assertContains(respuesta, '$25,00')
        self.assertContains(respuesta, 'SP')  # iniciales de Sofía Paredes


class MiHorarioTests(TestCase):
    """Mi horario (HU-26, RF-07 a RF-10). Las fechas se calculan desde hoy para que las pruebas no caduquen."""

    def setUp(self):
        self.sofia = crear_veterinario()
        self.client.force_login(self.sofia)
        self.hoy = timezone.localdate()
        self.lunes = self.hoy - timedelta(days=self.hoy.weekday())
        self.manana = self.hoy + timedelta(days=1)

    def agregar(self, fecha, inicio, fin):
        return self.client.post(reverse('citas:horario'), {
            'fecha': fecha.isoformat(), 'hora_inicio': inicio, 'hora_fin': fin,
        })

    def test_cliente_y_administrador_reciben_403(self):
        for usuario in [crear_usuario('ana'), crear_usuario('laura', rol=Roles.ADMINISTRADOR)]:
            self.client.force_login(usuario)
            with self.subTest(rol=usuario.rol):
                self.assertEqual(self.client.get(reverse('citas:horario')).status_code, 403)

    def test_agregar_un_bloque_lo_guarda_con_el_veterinario_de_la_sesion(self):
        respuesta = self.agregar(self.manana, '09:00', '12:00')
        self.assertRedirects(respuesta, f"{reverse('citas:horario')}?semana={(self.manana - timedelta(days=self.manana.weekday())).isoformat()}")
        bloque = HorarioVeterinario.objects.get()
        self.assertEqual(bloque.veterinario, self.sofia)
        self.assertEqual((bloque.hora_inicio, bloque.hora_fin), (time(9), time(12)))

    def test_no_se_puede_elegir_otro_veterinario(self):
        mateo = crear_veterinario('mateo')
        self.client.post(reverse('citas:horario'), {
            'fecha': self.manana.isoformat(), 'hora_inicio': '09:00', 'hora_fin': '12:00', 'veterinario': mateo.pk,
        })
        self.assertEqual(HorarioVeterinario.objects.get().veterinario, self.sofia)

    def test_fin_antes_del_inicio_se_rechaza(self):
        respuesta = self.agregar(self.manana, '12:00', '09:00')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('hora_fin', respuesta.context['form'].errors)
        self.assertFalse(HorarioVeterinario.objects.exists())

    def test_bloque_cruzado_se_rechaza(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        respuesta = self.agregar(self.manana, '11:00', '14:00')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Se cruza con otro bloque')
        self.assertEqual(HorarioVeterinario.objects.count(), 1)

    def test_bloque_seguido_si_se_acepta(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        self.agregar(self.manana, '12:00', '14:00')
        self.assertEqual(HorarioVeterinario.objects.count(), 2)

    def test_el_bloque_de_otro_veterinario_no_cuenta_como_cruce(self):
        crear_horario(crear_veterinario('mateo'), time(9), time(12), fecha=self.manana)
        self.agregar(self.manana, '09:00', '12:00')
        self.assertEqual(HorarioVeterinario.objects.filter(veterinario=self.sofia).count(), 1)

    def test_un_dia_que_ya_paso_se_rechaza(self):
        respuesta = self.agregar(self.hoy - timedelta(days=1), '09:00', '12:00')
        self.assertIn('fecha', respuesta.context['form'].errors)

    def test_la_semana_muestra_solo_mis_bloques(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.lunes)
        crear_horario(crear_veterinario('mateo'), time(15), time(18), fecha=self.lunes)
        respuesta = self.client.get(reverse('citas:horario'))
        bloques = [bloque for dia in respuesta.context['dias'] for bloque in dia['bloques']]
        self.assertEqual([bloque.veterinario for bloque in bloques], [self.sofia])
        self.assertEqual(respuesta.context['total_semana'], '3 h')
        self.assertNotContains(respuesta, '15:00')

    def test_la_semana_elegida_por_la_url(self):
        siguiente = self.lunes + timedelta(days=7)
        crear_horario(self.sofia, time(9), time(10, 30), fecha=siguiente + timedelta(days=2))
        respuesta = self.client.get(reverse('citas:horario'), {'semana': (siguiente + timedelta(days=4)).isoformat()})
        self.assertEqual(respuesta.context['lunes'], siguiente)
        self.assertEqual(respuesta.context['total_semana'], '1 h 30 min')
        # una fecha inventada vuelve a la semana actual
        self.assertEqual(self.client.get(reverse('citas:horario'), {'semana': 'x'}).context['lunes'], self.lunes)

    def test_un_veterinario_no_ve_ni_edita_ni_borra_el_horario_de_otro(self):
        bloque = crear_horario(crear_veterinario('mateo'), time(9), time(12), fecha=self.manana)
        editar = reverse('citas:horario_editar', args=[bloque.pk])
        self.assertEqual(self.client.get(editar).status_code, 404)
        self.assertEqual(self.client.post(editar, {'fecha': self.manana.isoformat(), 'hora_inicio': '07:00',
                                                   'hora_fin': '08:00'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('citas:horario_eliminar', args=[bloque.pk])).status_code, 404)
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, time(9))

    def test_editar_mi_bloque(self):
        bloque = crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        self.client.post(reverse('citas:horario_editar', args=[bloque.pk]),
                         {'fecha': self.manana.isoformat(), 'hora_inicio': '10:00', 'hora_fin': '13:00'})
        bloque.refresh_from_db()
        self.assertEqual((bloque.hora_inicio, bloque.hora_fin), (time(10), time(13)))

    def test_quitar_mi_bloque_solo_con_post(self):
        bloque = crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        url = reverse('citas:horario_eliminar', args=[bloque.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(HorarioVeterinario.objects.exists())

    def test_copiar_la_semana_anterior(self):
        siguiente = self.lunes + timedelta(days=7)
        crear_horario(self.sofia, time(9), time(12), fecha=self.lunes)
        crear_horario(self.sofia, time(14), time(18), fecha=self.lunes + timedelta(days=2))
        # ya existe un bloque que se cruza con el de las 14:00: ese no se copia
        crear_horario(self.sofia, time(15), time(16), fecha=siguiente + timedelta(days=2))
        self.client.post(reverse('citas:horario_copiar'), {'semana': siguiente.isoformat()})
        copiados = HorarioVeterinario.objects.filter(fecha__gte=siguiente).order_by('fecha', 'hora_inicio')
        self.assertEqual([(b.fecha, b.hora_inicio) for b in copiados],
                         [(siguiente, time(9)), (siguiente + timedelta(days=2), time(15))])

    def test_copiar_no_toca_el_horario_de_otro_veterinario(self):
        siguiente = self.lunes + timedelta(days=7)
        crear_horario(crear_veterinario('mateo'), time(9), time(12), fecha=self.lunes)
        self.client.post(reverse('citas:horario_copiar'), {'semana': siguiente.isoformat()})
        self.assertFalse(HorarioVeterinario.objects.filter(fecha__gte=siguiente).exists())

    def test_elegir_los_servicios_que_atiendo(self):
        consulta = crear_servicio()
        vacunacion = crear_servicio(nombre='Vacunación')
        inactivo = crear_servicio(nombre='Peluquería', activo=False)
        inactivo.veterinarios.add(self.sofia)
        respuesta = self.client.get(reverse('citas:horario'))
        self.assertContains(respuesta, f'type="checkbox" name="servicios" value="{consulta.pk}"')
        self.assertNotContains(respuesta, 'Peluquería')

        self.client.post(reverse('citas:mis_servicios'), {'servicios': [consulta.pk, vacunacion.pk]})
        self.assertEqual(set(self.sofia.servicios.all()), {consulta, vacunacion, inactivo})
        self.client.post(reverse('citas:mis_servicios'), {})
        self.assertEqual(list(self.sofia.servicios.all()), [inactivo])  # el inactivo se conserva

    def test_no_puede_marcar_un_servicio_inactivo(self):
        inactivo = crear_servicio(activo=False)
        self.client.post(reverse('citas:mis_servicios'), {'servicios': [inactivo.pk]})
        self.assertFalse(self.sofia.servicios.exists())

    def test_la_portada_del_veterinario_cuenta_sus_servicios(self):
        crear_servicio().veterinarios.add(self.sofia)
        respuesta = self.client.get(reverse('cuentas:inicio_veterinario'))
        self.assertEqual(respuesta.context['servicios_que_atiendo'], 1)
        self.assertContains(respuesta, reverse('citas:horario'))


# ---------------------------------------------------------------------------
# Core: AgendaService (turnos libres, agendar y cancelar)
# ---------------------------------------------------------------------------
class AgendaServiceTests(TestCase):
    """El veterinario atiende de 9:00 a 11:00 dentro de una semana; la consulta dura 30 minutos."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.mascota = crear_mascota(crear_usuario('ana'))

    def hora(self, horas, minutos=0):
        """Fecha y hora con zona horaria (America/Guayaquil), como las guarda la cita."""
        return timezone.make_aware(timezone.datetime.combine(self.fecha, time(horas, minutos)))

    def agendar(self, inicio, **datos):
        valores = {'mascota': self.mascota, 'veterinario': self.veterinario, 'servicio': self.servicio}
        valores.update(datos)
        return AgendaService.agendar(inicio=inicio, **valores)

    def test_corta_el_horario_en_turnos_del_largo_del_servicio(self):
        espacios = AgendaService.espacios_disponibles(self.veterinario, self.servicio, self.fecha)
        self.assertEqual(espacios, [self.hora(9), self.hora(9, 30), self.hora(10), self.hora(10, 30)])

    def test_un_turno_que_no_cabe_completo_no_se_ofrece(self):
        servicio_largo = crear_servicio(nombre='Cirugía menor', duracion_min=90)
        espacios = AgendaService.espacios_disponibles(self.veterinario, servicio_largo, self.fecha)
        self.assertEqual(espacios, [self.hora(9)])  # 10:30 + 90 min pasaría de las 11:00

    def test_agendar_crea_la_cita_confirmada_con_fin_y_precio(self):
        cita = self.agendar(self.hora(9, 30), motivo='Control anual')
        self.assertEqual(cita.estado, EstadoCita.CONFIRMADA)
        self.assertEqual(cita.fin, self.hora(10))
        self.assertEqual(cita.precio, Decimal('25.00'))

    def test_el_turno_agendado_deja_de_estar_libre(self):
        self.agendar(self.hora(9, 30))
        espacios = AgendaService.espacios_disponibles(self.veterinario, self.servicio, self.fecha)
        self.assertNotIn(self.hora(9, 30), espacios)

    def test_no_se_puede_agendar_un_turno_ocupado(self):
        self.agendar(self.hora(9, 30))
        otra_mascota = crear_mascota(crear_usuario('luis'), nombre='Michi')
        with self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
            self.agendar(self.hora(9, 30), mascota=otra_mascota)
        self.assertEqual(Cita.objects.count(), 1)

    def test_un_cruce_parcial_tambien_se_rechaza(self):
        # 9:15 no es un turno ofrecido y además se cruza con la cita de 9:00 a 9:30
        self.agendar(self.hora(9))
        with self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
            self.agendar(self.hora(9, 15))

    def test_fuera_del_horario_no_se_puede_agendar(self):
        with self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
            self.agendar(self.hora(15))

    def test_veterinario_que_no_atiende_el_servicio(self):
        otro = crear_veterinario('mario')
        crear_horario(otro, time(9, 0), time(11, 0), fecha=self.fecha)
        with self.assertRaisesMessage(ValidationError, 'no atiende este servicio'):
            self.agendar(self.hora(9), veterinario=otro)

    def test_servicio_desactivado_no_se_agenda(self):
        self.servicio.activo = False
        self.servicio.save()
        with self.assertRaisesMessage(ValidationError, 'ya no se ofrece'):
            self.agendar(self.hora(9))

    def test_hora_pasada_no_se_agenda(self):
        with self.assertRaisesMessage(ValidationError, 'todavía no haya pasado'):
            self.agendar(timezone.now() - timedelta(hours=1))

    def test_el_precio_queda_copiado(self):
        cita = self.agendar(self.hora(9))
        self.servicio.precio = Decimal('40.00')
        self.servicio.save()
        cita.refresh_from_db()
        self.assertEqual(cita.precio, Decimal('25.00'))

    def test_cancelar_libera_el_turno(self):
        cita = self.agendar(self.hora(9))
        AgendaService.cancelar(cita)
        self.assertEqual(cita.estado, EstadoCita.CANCELADA)
        # El mismo turno se puede volver a agendar: la UniqueConstraint ignora las canceladas
        self.assertEqual(self.agendar(self.hora(9)).estado, EstadoCita.CONFIRMADA)

    def test_una_cita_atendida_no_se_cancela(self):
        cita = self.agendar(self.hora(9))
        cita.estado = EstadoCita.ATENDIDA
        cita.save()
        with self.assertRaisesMessage(ValidationError, 'Solo se puede cancelar una cita confirmada'):
            AgendaService.cancelar(cita)

    def test_la_base_rechaza_dos_citas_activas_a_la_misma_hora(self):
        # Aunque alguien se salte AgendaService, la UniqueConstraint lo impide
        datos = {'mascota': self.mascota, 'veterinario': self.veterinario, 'servicio': self.servicio,
                 'inicio': self.hora(9), 'fin': self.hora(9, 30), 'precio': Decimal('25.00')}
        Cita.objects.create(**datos)
        with self.assertRaises(IntegrityError):
            Cita.objects.create(**datos)


class AgendarVistasTests(TestCase):
    """Agendar, horas libres, Mis citas y cancelar, desde el navegador del cliente."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.client.force_login(self.cliente)

    def datos(self, **cambios):
        valores = {'mascota': self.mascota.pk, 'servicio': self.servicio.pk, 'veterinario': self.veterinario.pk,
                   'fecha': self.fecha.isoformat(), 'hora': '09:30', 'motivo': 'Control'}
        valores.update(cambios)
        return valores

    def test_solo_el_cliente_puede_agendar(self):
        self.client.force_login(self.veterinario)
        self.assertEqual(self.client.get(reverse('citas:agendar')).status_code, 403)

    def test_agendar_crea_la_cita_y_va_a_mis_citas(self):
        respuesta = self.client.post(reverse('citas:agendar'), self.datos())
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        cita = Cita.objects.get()
        self.assertEqual(timezone.localtime(cita.inicio).time(), time(9, 30))

    def test_no_se_agenda_con_la_mascota_de_otro(self):
        ajena = crear_mascota(crear_usuario('luis'), nombre='Michi')
        respuesta = self.client.post(reverse('citas:agendar'), self.datos(mascota=ajena.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('mascota', respuesta.context['form'].errors)
        self.assertFalse(Cita.objects.exists())

    def test_veterinario_que_no_atiende_el_servicio_da_error(self):
        otro = crear_veterinario('mario')
        respuesta = self.client.post(reverse('citas:agendar'), self.datos(veterinario=otro.pk))
        self.assertIn('veterinario', respuesta.context['form'].errors)

    def test_fecha_pasada_da_error(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        respuesta = self.client.post(reverse('citas:agendar'), self.datos(fecha=ayer))
        self.assertIn('fecha', respuesta.context['form'].errors)

    def test_turno_ocupado_muestra_el_mensaje_del_core(self):
        self.client.post(reverse('citas:agendar'), self.datos())
        respuesta = self.client.post(reverse('citas:agendar'), self.datos())
        self.assertContains(respuesta, TURNO_OCUPADO)
        self.assertEqual(Cita.objects.count(), 1)

    def test_desde_el_popup_agendar_devuelve_la_confirmacion_en_json(self):
        respuesta = self.client.post(reverse('citas:agendar'), self.datos(), headers={'X-Requested-With': 'fetch'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.mascota.nombre, respuesta.json()['titulo'])
        self.assertEqual(Cita.objects.count(), 1)

    def test_desde_el_popup_con_errores_vuelve_solo_la_reserva(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        respuesta = self.client.post(reverse('citas:agendar'), self.datos(fecha=ayer), headers={'X-Requested-With': 'fetch'})
        self.assertContains(respuesta, 'data-agendar')
        self.assertNotContains(respuesta, '<html')   # el parcial, no la página entera
        self.assertFalse(Cita.objects.exists())

    def test_mis_citas_trae_la_reserva_para_el_popup(self):
        respuesta = self.client.get(reverse('citas:mis_citas'))
        self.assertContains(respuesta, 'data-dialogo-agendar')
        self.assertIn('form', respuesta.context)

    def test_turnos_del_dia_agrupados_por_veterinario(self):
        self.client.post(reverse('citas:agendar'), self.datos())
        otro = crear_veterinario('mario', first_name='Mario', last_name='Ruiz')
        self.servicio.veterinarios.add(otro)
        crear_horario(otro, time(10, 0), time(11, 0), fecha=self.fecha)
        respuesta = self.client.get(reverse('citas:turnos_del_dia'), {'servicio': self.servicio.pk, 'fecha': self.fecha.isoformat()})
        turnos = {grupo['veterinario']: grupo['horas'] for grupo in respuesta.json()['turnos']}
        self.assertEqual(turnos, {self.veterinario.pk: ['09:00', '10:00', '10:30'], otro.pk: ['10:00', '10:30']})

    def test_turnos_con_datos_inventados_devuelve_vacio(self):
        respuesta = self.client.get(reverse('citas:turnos_del_dia'), {'servicio': 999, 'fecha': 'ayer'})
        self.assertEqual(respuesta.json(), {'turnos': []})

    def test_mis_citas_muestra_solo_las_propias(self):
        self.client.post(reverse('citas:agendar'), self.datos())
        ajena = crear_mascota(crear_usuario('luis'), nombre='Michi')
        AgendaService.agendar(ajena, self.veterinario, self.servicio,
                              timezone.make_aware(timezone.datetime.combine(self.fecha, time(10, 0))))
        respuesta = self.client.get(reverse('citas:mis_citas'))
        self.assertEqual([c.mascota for c in respuesta.context['proximas']], [self.mascota])

    def test_cancelar_por_post_libera_el_turno(self):
        self.client.post(reverse('citas:agendar'), self.datos())
        cita = Cita.objects.get()
        respuesta = self.client.post(reverse('citas:cancelar', args=[cita.pk]))
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.CANCELADA)

    def test_cancelar_la_cita_de_otro_responde_404(self):
        ajena = crear_mascota(crear_usuario('luis'), nombre='Michi')
        cita = AgendaService.agendar(ajena, self.veterinario, self.servicio,
                                     timezone.make_aware(timezone.datetime.combine(self.fecha, time(10, 0))))
        respuesta = self.client.post(reverse('citas:cancelar', args=[cita.pk]))
        self.assertEqual(respuesta.status_code, 404)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.CONFIRMADA)


class CalendarioYAgendaTests(TestCase):
    """Días con turnos libres (calendario), la agenda del veterinario y el cierre de cada cita."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(10, 0), fecha=self.fecha)
        self.mascota = crear_mascota(crear_usuario('ana'))

    def hora(self, fecha, horas, minutos=0):
        return timezone.make_aware(timezone.datetime.combine(fecha, time(horas, minutos)))

    def cita_pasada(self):
        """Una cita confirmada de hace una hora (se crea directo: agendar() no acepta horas pasadas)."""
        inicio = timezone.now() - timedelta(hours=1)
        return Cita.objects.create(mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
                                   inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'))

    def test_un_dia_lleno_no_aparece_en_el_calendario(self):
        mes = (self.fecha.year, self.fecha.month)
        self.assertEqual(AgendaService.dias_disponibles(self.veterinario, self.servicio, *mes), [self.fecha])
        AgendaService.agendar(self.mascota, self.veterinario, self.servicio, self.hora(self.fecha, 9))
        AgendaService.agendar(self.mascota, self.veterinario, self.servicio, self.hora(self.fecha, 9, 30))
        self.assertEqual(AgendaService.dias_disponibles(self.veterinario, self.servicio, *mes), [])

    def test_dias_disponibles_en_json(self):
        self.client.force_login(self.mascota.dueno)
        respuesta = self.client.get(reverse('citas:dias_disponibles'), {
            'servicio': self.servicio.pk, 'mes': self.fecha.strftime('%Y-%m'),
        })
        self.assertEqual(respuesta.json(), {'dias': [self.fecha.isoformat()]})
        respuesta = self.client.get(reverse('citas:dias_disponibles'), {'mes': 'nada'})
        self.assertEqual(respuesta.json(), {'dias': []})

    def test_cerrar_una_cita_que_ya_empezo(self):
        cita = AgendaService.registrar_resultado(self.cita_pasada(), EstadoCita.ATENDIDA)
        self.assertEqual(cita.estado, EstadoCita.ATENDIDA)

    def test_no_se_cierra_antes_de_su_hora(self):
        cita = AgendaService.agendar(self.mascota, self.veterinario, self.servicio, self.hora(self.fecha, 9))
        with self.assertRaisesMessage(ValidationError, 'todavía no empieza'):
            AgendaService.registrar_resultado(cita, EstadoCita.ATENDIDA)

    def test_no_se_cierra_dos_veces_ni_con_un_estado_inventado(self):
        cita = AgendaService.registrar_resultado(self.cita_pasada(), EstadoCita.NO_ASISTIO)
        with self.assertRaisesMessage(ValidationError, 'ya fue cerrada'):
            AgendaService.registrar_resultado(cita, EstadoCita.ATENDIDA)
        with self.assertRaisesMessage(ValidationError, 'no es válido'):
            AgendaService.registrar_resultado(cita, 'perdida')

    def test_la_agenda_es_solo_del_veterinario(self):
        self.client.force_login(self.mascota.dueno)
        self.assertEqual(self.client.get(reverse('citas:agenda')).status_code, 403)

    def test_la_agenda_muestra_las_citas_del_dia(self):
        AgendaService.agendar(self.mascota, self.veterinario, self.servicio, self.hora(self.fecha, 9))
        self.client.force_login(self.veterinario)
        respuesta = self.client.get(reverse('citas:agenda'), {'fecha': self.fecha.isoformat()})
        self.assertEqual(len(respuesta.context['citas']), 1)
        self.assertContains(respuesta, 'Por atender')

    def test_marcar_atendida_desde_la_agenda(self):
        cita = self.cita_pasada()
        self.client.force_login(self.veterinario)
        self.client.post(reverse('citas:resultado', args=[cita.pk]), {'estado': EstadoCita.ATENDIDA})
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.ATENDIDA)

    def test_otro_veterinario_no_cierra_la_cita(self):
        cita = self.cita_pasada()
        self.client.force_login(crear_veterinario('mario'))
        respuesta = self.client.post(reverse('citas:resultado', args=[cita.pk]), {'estado': EstadoCita.ATENDIDA})
        self.assertEqual(respuesta.status_code, 404)


class EstadisticasVeterinarioTests(TestCase):
    """El inicio del veterinario cuenta sus citas reales del período (las canceladas no cuentan)."""

    def test_cifras_del_periodo(self):
        veterinario = crear_veterinario()
        servicio = crear_servicio()
        mascota = crear_mascota(crear_usuario('ana'))
        ayer = timezone.now() - timedelta(days=1)
        for estado in (EstadoCita.ATENDIDA, EstadoCita.ATENDIDA, EstadoCita.NO_ASISTIO, EstadoCita.CANCELADA):
            ayer += timedelta(minutes=30)
            Cita.objects.create(mascota=mascota, veterinario=veterinario, servicio=servicio, inicio=ayer,
                                fin=ayer + timedelta(minutes=30), precio=Decimal('25.00'), estado=estado)

        self.client.force_login(veterinario)
        estadisticas = self.client.get(reverse('cuentas:inicio_veterinario')).context['estadisticas']
        self.assertEqual(estadisticas['citas'], 3)
        self.assertEqual(estadisticas['atendidas'], 2)
        self.assertEqual(estadisticas['no_asistio'], 1)
        self.assertEqual(estadisticas['ganancias'], Decimal('50.00'))


class PacientesTests(TestCase):
    """El veterinario busca mascotas y a sus dueños; un cliente no entra (403)."""

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.ana = crear_usuario('ana', first_name='Ana', last_name='Pérez')
        self.firulais = crear_mascota(self.ana, nombre='Firulais')
        crear_mascota(crear_usuario('luis', first_name='Luis'), nombre='Michi')
        self.client.force_login(self.veterinario)

    def test_un_cliente_no_entra(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('citas:pacientes')).status_code, 403)

    def test_busca_por_nombre_de_la_mascota(self):
        respuesta = self.client.get(reverse('citas:pacientes'), {'q': 'firu'})
        self.assertEqual(list(respuesta.context['mascotas']), [self.firulais])

    def test_busca_por_cedula_del_dueno(self):
        respuesta = self.client.get(reverse('citas:pacientes'), {'q': self.ana.cedula})
        self.assertEqual(list(respuesta.context['mascotas']), [self.firulais])

    def test_solo_mis_pacientes(self):
        inicio = timezone.now() - timedelta(days=1)
        Cita.objects.create(mascota=self.firulais, veterinario=self.veterinario, servicio=crear_servicio(),
                            inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'))
        respuesta = self.client.get(reverse('citas:pacientes'), {'mios': '1'})
        self.assertEqual(list(respuesta.context['mascotas']), [self.firulais])
        self.assertEqual(respuesta.context['mascotas'][0].citas_conmigo, 1)

    def test_el_veterinario_ve_la_foto_de_un_paciente(self):
        self.firulais.foto = b'imagen'
        self.firulais.save()
        self.assertEqual(self.client.get(reverse('mascotas:foto', args=[self.firulais.pk])).status_code, 200)
