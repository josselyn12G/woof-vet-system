import threading
import time as time_module
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cuentas.models import PerfilVeterinario, Roles
from mascotas.tests import crear_mascota, crear_usuario

from .models import Calificacion, Cita, EstadoCita, HorarioVeterinario, Notificacion, Servicio, TipoNotificacion
from .services import (
    ANTICIPACION_MINIMA, SIN_ANTICIPACION, TURNO_OCUPADO, AgendaService, CalificacionService, EstadisticasService,
    HorarioService, NotificacionService, ServicioService,
)


def crear_veterinario(username='sofia', verificado=True, **datos):
    """Un veterinario ya verificado (como los de la demo); con verificado=False, uno recién creado."""
    veterinario = crear_usuario(username, rol=Roles.VETERINARIO, **datos)
    PerfilVeterinario.objects.create(usuario=veterinario, verificado=verificado)
    return veterinario


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
        self.assertNotContains(respuesta, '15:00 – 18:00')   # el bloque de Mateo no aparece

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
        respuesta = self.client.get(reverse('panel:inicio_veterinario'))
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
        with self.assertRaisesMessage(ValidationError, SIN_ANTICIPACION):
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


class ReprogramarTests(TestCase):
    """
    Reprogramar (t67): mover una cita a otro día u hora en una sola operación.
    Si algo falla, la cita sigue en su hora de antes: nunca se pierde la reserva.
    """

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.cita = AgendaService.agendar(
            mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio, inicio=self.hora(9),
            motivo='Control',
        )
        self.url = reverse('citas:reprogramar', args=[self.cita.pk])

    def hora(self, horas, minutos=0):
        return timezone.make_aware(datetime.combine(self.fecha, time(horas, minutos)))

    def ocupar(self, inicio):
        """Otra mascota toma ese turno con el mismo veterinario."""
        return AgendaService.agendar(
            mascota=crear_mascota(crear_usuario('luis'), nombre='Toby'), veterinario=self.veterinario,
            servicio=self.servicio, inicio=inicio,
        )

    # ---------- El service ----------
    def test_mueve_la_misma_cita_y_conserva_sus_datos(self):
        cita = AgendaService.reprogramar(self.cita, self.hora(10))
        self.assertEqual(cita.pk, self.cita.pk)
        self.assertEqual(Cita.objects.count(), 1)           # no se creó otra fila
        cita.refresh_from_db()
        self.assertEqual(cita.inicio, self.hora(10))
        self.assertEqual(cita.fin, self.hora(10, 30))
        self.assertEqual((cita.precio, cita.motivo, cita.estado), (Decimal('25.00'), 'Control', EstadoCita.CONFIRMADA))

    def test_su_propio_turno_no_cuenta_como_ocupado(self):
        # 9:30 queda pegado a su turno actual (9:00-9:30): no choca consigo misma
        AgendaService.reprogramar(self.cita, self.hora(9, 30))
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.inicio, self.hora(9, 30))

    def test_si_el_turno_esta_ocupado_la_cita_se_queda_en_su_hora(self):
        self.ocupar(self.hora(10))
        with self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
            AgendaService.reprogramar(self.cita, self.hora(10))
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.inicio, self.hora(9))
        self.assertEqual(self.cita.estado, EstadoCita.CONFIRMADA)

    def test_si_la_base_rechaza_el_cambio_se_deshace_todo(self):
        # Simula el choque que atrapa la UniqueConstraint (dos pestañas a la vez): ROLLBACK
        with patch.object(Cita, 'save', side_effect=IntegrityError):
            with self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
                AgendaService.reprogramar(self.cita, self.hora(10))
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.inicio, self.hora(9))

    def test_rechaza_una_hora_fuera_del_horario_o_que_no_es_turno(self):
        for inicio in (self.hora(11), self.hora(9, 10)):
            with self.subTest(inicio=inicio), self.assertRaisesMessage(ValidationError, TURNO_OCUPADO):
                AgendaService.reprogramar(self.cita, inicio)

    def test_rechaza_la_misma_hora_y_una_hora_pasada(self):
        with self.assertRaisesMessage(ValidationError, 'Esa ya es la hora de la cita'):
            AgendaService.reprogramar(self.cita, self.hora(9))
        with self.assertRaisesMessage(ValidationError, SIN_ANTICIPACION):
            AgendaService.reprogramar(self.cita, timezone.now() - timedelta(hours=1))

    def test_una_cita_cancelada_o_que_ya_empezo_no_se_reprograma(self):
        AgendaService.cancelar(self.cita)
        with self.assertRaisesMessage(ValidationError, 'Solo se puede reprogramar'):
            AgendaService.reprogramar(self.cita, self.hora(10))

        empezada = Cita.objects.create(
            mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
            inicio=timezone.now() - timedelta(minutes=10), fin=timezone.now() + timedelta(minutes=20), precio=25,
        )
        self.assertFalse(AgendaService.se_puede_reprogramar(empezada))

    def test_la_pagina_muestra_la_cita_actual_y_el_recuadro_de_la_nueva_fecha(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Tu cita ahora')
        self.assertContains(respuesta, 'Consulta general')
        self.assertContains(respuesta, '09:00 – 09:30')       # el rango de la cita, no solo la hora
        self.assertContains(respuesta, '$25,00')
        self.assertContains(respuesta, '«Control»')            # el motivo se mantiene y se muestra
        self.assertContains(respuesta, 'data-nueva-texto')     # reprogramar.js escribe ahí la nueva fecha

    def test_las_horas_para_reprogramar_no_incluyen_la_actual(self):
        horas = AgendaService.horas_para_reprogramar(self.cita, self.fecha)
        self.assertEqual(horas, [self.hora(9, 30), self.hora(10), self.hora(10, 30)])
        self.assertIn(self.fecha, AgendaService.dias_para_reprogramar(self.cita, self.fecha.year, self.fecha.month))

    # ---------- Las vistas ----------
    def test_reprogramar_por_post_mueve_la_cita_y_va_a_mis_citas(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(self.url, {'fecha': self.fecha.isoformat(), 'hora': '10:30'})
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.inicio, self.hora(10, 30))

    def test_con_turno_ocupado_muestra_el_error_y_no_cambia_nada(self):
        self.ocupar(self.hora(10))
        self.client.force_login(self.cliente)
        respuesta = self.client.post(self.url, {'fecha': self.fecha.isoformat(), 'hora': '10:00'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, TURNO_OCUPADO)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.inicio, self.hora(9))

    def test_la_pagina_muestra_la_cita_y_mis_citas_enlaza_a_ella(self):
        self.client.force_login(self.cliente)
        self.assertContains(self.client.get(self.url), 'Tu cita ahora')
        self.assertContains(self.client.get(reverse('citas:mis_citas')), self.url)

    def test_una_cita_cancelada_vuelve_a_mis_citas_con_aviso(self):
        AgendaService.cancelar(self.cita)
        self.client.force_login(self.cliente)
        self.assertRedirects(self.client.get(self.url), reverse('citas:mis_citas'))

    def test_la_cita_de_otro_cliente_responde_404(self):
        self.client.force_login(crear_usuario('luis'))
        for url in (self.url, reverse('citas:reprogramar_horas', args=[self.cita.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'fecha': self.fecha.isoformat(), 'hora': '10:00'}).status_code,
                         404)

    def test_otros_roles_reciben_403(self):
        self.client.force_login(self.veterinario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_json_de_dias_y_horas(self):
        self.client.force_login(self.cliente)
        horas = self.client.get(reverse('citas:reprogramar_horas', args=[self.cita.pk]), {'fecha': self.fecha.isoformat()})
        self.assertEqual(horas.json(), {'horas': ['09:30', '10:00', '10:30']})
        dias = self.client.get(reverse('citas:reprogramar_dias', args=[self.cita.pk]),
                               {'mes': f'{self.fecha:%Y-%m}'})
        self.assertIn(self.fecha.isoformat(), dias.json()['dias'])
        self.assertEqual(self.client.get(reverse('citas:reprogramar_dias', args=[self.cita.pk]),
                                         {'mes': 'inventado'}).json(), {'dias': []})


class AnticipacionMinimaTests(TestCase):
    """
    RF-12 (§2.1 paso d.1): un turno nuevo se reserva con al menos 1 hora de anticipación.
    El reloj se congela con patch para reproducir el ejemplo del documento: Ana entra a las 08:20.
    """

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.mascota = crear_mascota(crear_usuario('ana'))

    def hora(self, horas, minutos=0):
        return timezone.make_aware(datetime.combine(self.fecha, time(horas, minutos)))

    def a_las(self, horas, minutos=0):
        """Hace que timezone.now() devuelva esa hora del día de la cita mientras dure el with."""
        return patch('django.utils.timezone.now', return_value=self.hora(horas, minutos))

    def agendar(self, inicio):
        return AgendaService.agendar(mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
                                     inicio=inicio)

    def espacios(self):
        return AgendaService.espacios_disponibles(self.veterinario, self.servicio, self.fecha)

    def test_la_anticipacion_es_de_una_hora(self):
        self.assertEqual(ANTICIPACION_MINIMA, timedelta(hours=1))

    def test_a_las_8_20_no_se_ofrece_el_turno_de_las_9(self):
        # Ejemplo del documento: a las 9:00 le faltan solo 40 minutos, así que se descarta
        with self.a_las(8, 20):
            self.assertEqual(self.espacios(), [self.hora(9, 30), self.hora(10), self.hora(10, 30)])

    def test_si_falta_exactamente_una_hora_el_turno_se_ofrece(self):
        with self.a_las(8, 0):
            self.assertIn(self.hora(9), self.espacios())

    def test_agendar_a_40_minutos_se_rechaza(self):
        with self.a_las(8, 20), self.assertRaisesMessage(ValidationError, SIN_ANTICIPACION):
            self.agendar(self.hora(9))
        self.assertFalse(Cita.objects.exists())

    def test_agendar_con_mas_de_una_hora_se_acepta(self):
        with self.a_las(8, 20):
            self.assertEqual(self.agendar(self.hora(9, 30)).estado, EstadoCita.CONFIRMADA)

    def test_reprogramar_a_menos_de_una_hora_se_rechaza_y_la_cita_conserva_su_hora(self):
        cita = self.agendar(self.hora(10, 30))
        with self.a_las(9, 50), self.assertRaisesMessage(ValidationError, SIN_ANTICIPACION):
            AgendaService.reprogramar(cita, self.hora(10))
        cita.refresh_from_db()
        self.assertEqual(cita.inicio, self.hora(10, 30))

    def test_cancelar_sigue_permitido_hasta_la_hora_de_inicio(self):
        # La anticipación es para elegir un turno nuevo; una cita que ya existe se cancela hasta que empieza
        cita = self.agendar(self.hora(9, 30))
        with self.a_las(9, 0):
            AgendaService.cancelar(cita)
        self.assertEqual(cita.estado, EstadoCita.CANCELADA)


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
        estadisticas = self.client.get(reverse('panel:inicio_veterinario')).context['estadisticas']
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


# ---------------------------------------------------------------------------
# Servicios del horario y de las estadísticas (fuera de las vistas)
# ---------------------------------------------------------------------------
class HorarioServiceTests(TestCase):
    """Copiar la semana y guardar los servicios que atiende, probados sin pasar por la vista."""

    def setUp(self):
        self.sofia = crear_veterinario()
        hoy = timezone.localdate()
        self.siguiente = hoy - timedelta(days=hoy.weekday()) + timedelta(days=7)   # el lunes que viene
        self.anterior = self.siguiente - timedelta(days=7)

    def test_copiar_semana_devuelve_copiados_y_omitidos(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.anterior + timedelta(days=4))
        crear_horario(self.sofia, time(14), time(18), fecha=self.anterior + timedelta(days=2))
        # ya hay un bloque que se cruza con el de las 14:00: ese se omite
        crear_horario(self.sofia, time(15), time(16), fecha=self.siguiente + timedelta(days=2))
        self.assertEqual(HorarioService.copiar_semana(self.sofia, self.siguiente), (1, 1))

    def test_copiar_sin_bloques_en_la_semana_anterior(self):
        with self.assertRaisesMessage(ValidationError, 'La semana anterior no tiene bloques para copiar.'):
            HorarioService.copiar_semana(self.sofia, self.siguiente)

    def test_guardar_servicios_conserva_los_inactivos(self):
        consulta = crear_servicio()
        inactivo = crear_servicio(nombre='Peluquería', activo=False)
        inactivo.veterinarios.add(self.sofia)
        HorarioService.guardar_servicios(self.sofia, [consulta])
        self.assertEqual(set(self.sofia.servicios.all()), {consulta, inactivo})


class EstadisticasServiceTests(TestCase):
    """Las cifras de la portada del veterinario se calculan sin pasar por la vista."""

    def test_cifras_del_periodo_y_del_anterior(self):
        veterinario = crear_veterinario()
        servicio = crear_servicio()
        mascota = crear_mascota(crear_usuario('ana'))
        hoy = timezone.localdate()
        for dias_atras, estado in ((1, EstadoCita.ATENDIDA), (2, EstadoCita.CANCELADA), (10, EstadoCita.ATENDIDA)):
            inicio = timezone.make_aware(timezone.datetime.combine(hoy - timedelta(days=dias_atras), time(10)))
            Cita.objects.create(mascota=mascota, veterinario=veterinario, servicio=servicio, inicio=inicio,
                                fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'), estado=estado)

        cifras = EstadisticasService.del_veterinario(veterinario, hoy - timedelta(days=6), hoy)
        self.assertEqual(len(cifras['fechas']), 7)
        self.assertEqual(cifras['actual']['citas'], 1)        # la cancelada no cuenta
        self.assertEqual(cifras['actual']['ganancias'], Decimal('25.00'))
        self.assertEqual(cifras['anterior']['atendidas'], 1)   # la de hace 10 días es del período anterior

# ---------------------------------------------------------------------------
# Mi horario en columnas y gestión de la clínica (administrador y superadministrador)
# ---------------------------------------------------------------------------
class SemanaEnColumnasTests(TestCase):
    """La grilla de Mi horario: cada bloque trae su posición, su duración y cuántas citas tiene."""

    def setUp(self):
        self.sofia = crear_veterinario()
        self.client.force_login(self.sofia)
        self.manana = timezone.localdate() + timedelta(days=1)

    def test_cada_bloque_trae_su_posicion_en_la_grilla(self):
        # La grilla va de 07:00 a 19:00 (12 h): un bloque de 13:00 a 16:00 empieza a la mitad y ocupa un cuarto
        crear_horario(self.sofia, time(13), time(16), fecha=self.manana)
        respuesta = self.client.get(reverse('citas:horario'), {'semana': self.manana.isoformat()})
        bloque = next(b for dia in respuesta.context['dias'] for b in dia['bloques'])
        self.assertEqual((bloque.arriba, bloque.alto, bloque.duracion), (50, 25, '3 h'))
        self.assertEqual(respuesta.context['horas_grilla'][0], '07:00')

    def test_la_grilla_se_estira_si_un_bloque_empieza_temprano(self):
        crear_horario(self.sofia, time(6), time(8), fecha=self.manana)
        respuesta = self.client.get(reverse('citas:horario'), {'semana': self.manana.isoformat()})
        self.assertEqual(respuesta.context['horas_grilla'][0], '06:00')

    def test_el_bloque_cuenta_sus_citas(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        servicio = crear_servicio()
        servicio.veterinarios.add(self.sofia)
        inicio = timezone.make_aware(datetime.combine(self.manana, time(10)))
        AgendaService.agendar(crear_mascota(crear_usuario('ana')), self.sofia, servicio, inicio)
        respuesta = self.client.get(reverse('citas:horario'), {'semana': self.manana.isoformat()})
        bloque = next(b for dia in respuesta.context['dias'] for b in dia['bloques'])
        self.assertEqual(bloque.citas, 1)

    def test_el_mas_de_un_dia_de_la_grilla_llena_la_fecha_del_formulario(self):
        respuesta = self.client.get(reverse('citas:horario'), {'fecha': self.manana.isoformat()})
        self.assertEqual(respuesta.context['form'].initial['fecha'], self.manana)
        # un día que ya pasó no se sugiere
        ayer = timezone.localdate() - timedelta(days=1)
        respuesta = self.client.get(reverse('citas:horario'), {'fecha': ayer.isoformat()})
        self.assertNotEqual(respuesta.context['form'].initial['fecha'], ayer)


class GestionCitasTests(TestCase):
    def setUp(self):
        self.administrador = crear_usuario('laura', rol=Roles.ADMINISTRADOR)
        self.sofia = crear_veterinario()
        self.servicio = crear_servicio()
        self.mascota = crear_mascota(crear_usuario('ana', first_name='Ana'))
        ahora = timezone.now()
        self.proxima = Cita.objects.create(mascota=self.mascota, veterinario=self.sofia, servicio=self.servicio,
                                           inicio=ahora + timedelta(days=2), fin=ahora + timedelta(days=2, minutes=30),
                                           precio=Decimal('25.00'))
        self.pasada = Cita.objects.create(mascota=self.mascota, veterinario=self.sofia, servicio=self.servicio,
                                          inicio=ahora - timedelta(days=2), fin=ahora - timedelta(days=2) + timedelta(minutes=30),
                                          precio=Decimal('25.00'), estado=EstadoCita.ATENDIDA)
        self.client.force_login(self.administrador)

    def test_solo_entran_el_administrador_y_el_superadministrador(self):
        for usuario, codigo in [(self.sofia, 403), (self.mascota.dueno, 403),
                                (crear_usuario('sara', rol=Roles.SUPERADMIN), 200)]:
            self.client.force_login(usuario)
            for nombre in ('citas:gestion_citas', 'citas:gestion_horarios'):
                with self.subTest(rol=usuario.rol, pantalla=nombre):
                    self.assertEqual(self.client.get(reverse(nombre)).status_code, codigo)

    def test_pestanas_proximas_pasadas_y_todas(self):
        url = reverse('citas:gestion_citas')
        self.assertEqual(list(self.client.get(url).context['citas']), [self.proxima])
        self.assertEqual(list(self.client.get(url, {'vista': 'pasadas'}).context['citas']), [self.pasada])
        self.assertEqual(len(self.client.get(url, {'vista': 'todas'}).context['citas']), 2)
        # una pestaña inventada vuelve a Próximas
        self.assertEqual(self.client.get(url, {'vista': 'nada'}).context['vista'], 'proximas')

    def test_filtros_por_estado_veterinario_y_busqueda(self):
        url = reverse('citas:gestion_citas')
        self.assertEqual(list(self.client.get(url, {'vista': 'todas', 'estado': 'atendida'}).context['citas']), [self.pasada])
        self.assertEqual(len(self.client.get(url, {'vista': 'todas', 'veterinario': crear_veterinario('mateo').pk})
                             .context['citas']), 0)
        self.assertEqual(len(self.client.get(url, {'vista': 'todas', 'q': 'firu'}).context['citas']), 2)
        # valores inventados en la URL se ignoran: no rompen la página
        self.assertEqual(len(self.client.get(url, {'vista': 'todas', 'estado': 'perdida', 'veterinario': 'x'})
                             .context['citas']), 2)

    def test_resumen_de_la_clinica(self):
        resumen = self.client.get(reverse('citas:gestion_citas')).context['resumen']
        self.assertEqual((resumen['semana'], resumen['atendidas'], resumen['ingresos']), (1, 1, Decimal('25.00')))

    def test_el_administrador_cancela_una_cita(self):
        respuesta = self.client.post(reverse('citas:gestion_cancelar', args=[self.proxima.pk]),
                                     {'volver': 'https://otro-sitio.com/'})
        self.assertRedirects(respuesta, reverse('citas:gestion_citas'))   # nunca vuelve a una URL de afuera
        self.proxima.refresh_from_db()
        self.assertEqual(self.proxima.estado, EstadoCita.CANCELADA)

    def test_no_cancela_una_cita_que_ya_paso(self):
        self.client.post(reverse('citas:gestion_cancelar', args=[self.pasada.pk]))
        self.pasada.refresh_from_db()
        self.assertEqual(self.pasada.estado, EstadoCita.ATENDIDA)

    def test_horarios_de_la_clinica_por_veterinario(self):
        crear_veterinario('mateo')
        manana = timezone.localdate() + timedelta(days=1)
        crear_horario(self.sofia, time(9), time(13), fecha=manana)
        contexto = self.client.get(reverse('citas:gestion_horarios'), {'semana': manana.isoformat()}).context
        filas = {fila['veterinario'].username: fila for fila in contexto['filas']}
        self.assertEqual(filas['sofia']['total'], '4 h')
        self.assertTrue(filas['mateo']['sin_horario'])
        self.assertEqual((contexto['resumen']['con_horario'], contexto['resumen']['veterinarios']), (1, 2))


class MiSemanaTests(TestCase):
    """El inicio del veterinario: los 7 días con su horario de fondo y las citas reservadas encima, con su detalle."""

    def setUp(self):
        self.sofia = crear_veterinario(first_name='Sofía')
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.sofia)
        self.ana = crear_usuario('ana', first_name='Ana', telefono='+593991112233')
        self.mascota = crear_mascota(self.ana, nombre='Firulais')
        self.manana = timezone.localdate() + timedelta(days=1)
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        self.client.force_login(self.sofia)

    def cita(self, hora, veterinario=None, **datos):
        inicio = timezone.make_aware(datetime.combine(self.manana, hora))
        return Cita.objects.create(mascota=self.mascota, veterinario=veterinario or self.sofia, servicio=self.servicio,
                                   inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'), **datos)

    def semana(self):
        return self.client.get(reverse('panel:inicio_veterinario'), {'semana': self.manana.isoformat()}).context['semana']

    def test_muestra_los_7_dias_con_el_horario(self):
        semana = self.semana()
        self.assertEqual(len(semana['dias']), 7)
        dia = next(d for d in semana['dias'] if d['fecha'] == self.manana)
        self.assertEqual([(b.hora_inicio, b.hora_fin) for b in dia['bloques']], [(time(9), time(12))])

    def test_las_citas_reservadas_van_en_su_dia_y_su_hora(self):
        cita = self.cita(time(10, 30), motivo='Tose mucho')
        dia = next(d for d in self.semana()['dias'] if d['fecha'] == self.manana)
        self.assertEqual(dia['citas'], [cita])
        # La grilla va de 07:00 a 19:00 (720 min): las 10:30 están a 210 min, un 29,167 %
        self.assertEqual((dia['citas'][0].arriba, dia['citas'][0].duracion), (29.167, '30 min'))

    def test_no_muestra_canceladas_ni_citas_de_otro_veterinario(self):
        self.cita(time(9), estado=EstadoCita.CANCELADA)
        self.cita(time(11), veterinario=crear_veterinario('mateo'))
        self.assertEqual(self.semana()['citas_semana'], 0)

    def test_el_detalle_de_la_cita_esta_en_la_pagina(self):
        cita = self.cita(time(10, 30), motivo='Tose mucho')
        respuesta = self.client.get(reverse('panel:inicio_veterinario'), {'semana': self.manana.isoformat()})
        # Pop-up nativo: el botón de la cita lo abre sin JavaScript y sin cambiar de página
        self.assertContains(respuesta, f'popovertarget="detalle-cita-{cita.pk}"')
        self.assertContains(respuesta, f'id="detalle-cita-{cita.pk}" popover')
        self.assertContains(respuesta, 'Tose mucho')
        self.assertContains(respuesta, '10:30 – 11:00')
        self.assertContains(respuesta, 'tel:+593991112233')

    def test_una_semana_inventada_vuelve_a_la_actual(self):
        respuesta = self.client.get(reverse('panel:inicio_veterinario'), {'semana': 'nada'})
        self.assertTrue(respuesta.context['semana']['es_semana_actual'])


class AgendaDelDiaTests(TestCase):
    """La agenda del veterinario: foto de la mascota, resumen por estado, la semana y las citas por cerrar."""

    def setUp(self):
        self.sofia = crear_veterinario()
        self.servicio = crear_servicio()
        self.mascota = crear_mascota(crear_usuario('ana'), nombre='Firulais')
        self.ayer = timezone.localdate() - timedelta(days=1)
        self.client.force_login(self.sofia)

    def cita(self, hora, **datos):
        inicio = timezone.make_aware(datetime.combine(self.ayer, hora))
        return Cita.objects.create(mascota=self.mascota, veterinario=self.sofia, servicio=self.servicio, inicio=inicio,
                                   fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'), **datos)

    def agenda(self):
        return self.client.get(reverse('citas:agenda'), {'fecha': self.ayer.isoformat()})

    def test_muestra_la_foto_de_la_mascota(self):
        self.mascota.foto = b'imagen'
        self.mascota.save()
        self.cita(time(9))
        self.assertContains(self.agenda(), reverse('mascotas:foto', args=[self.mascota.pk]))

    def test_sin_foto_muestra_la_inicial(self):
        self.cita(time(9))
        respuesta = self.agenda()
        self.assertNotContains(respuesta, reverse('mascotas:foto', args=[self.mascota.pk]))
        self.assertContains(respuesta, 'avatar-inicial')

    def test_resumen_y_avance_del_dia(self):
        self.cita(time(9), estado=EstadoCita.ATENDIDA)
        self.cita(time(10), estado=EstadoCita.NO_ASISTIO)
        self.cita(time(11))
        self.cita(time(12), estado=EstadoCita.CANCELADA)
        contexto = self.agenda().context
        self.assertEqual(contexto['activas'], 3)
        self.assertEqual(contexto['resumen'], {'por_atender': 1, 'atendidas': 1, 'no_asistio': 1, 'canceladas': 1,
                                               'avance': 67})

    def test_una_cita_que_ya_empezo_queda_por_cerrar(self):
        self.cita(time(9))
        respuesta = self.agenda()
        self.assertTrue(respuesta.context['citas'][0].puede_cerrarse)
        self.assertContains(respuesta, 'Por cerrar')

    def test_la_semana_cuenta_las_citas_de_cada_dia(self):
        self.cita(time(9))
        self.cita(time(10), estado=EstadoCita.CANCELADA)   # las canceladas no cuentan
        semana = self.agenda().context['semana_agenda']
        self.assertEqual(len(semana), 7)
        elegido = next(dia for dia in semana if dia['es_elegido'])
        self.assertEqual((elegido['fecha'], elegido['citas']), (self.ayer, 1))


class GestionHorarioVeterinarioTests(TestCase):
    """El superadministrador edita el horario y los servicios de cualquier veterinario desde Horarios."""

    def setUp(self):
        self.superadmin = crear_usuario('sara', rol=Roles.SUPERADMIN)
        self.sofia = crear_veterinario(first_name='Sofía', last_name='Mora')
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.superadmin)

    def url(self, nombre, *args):
        return reverse(f'citas:{nombre}', args=[self.sofia.pk, *args])

    def semana(self, fecha):
        return f"{self.url('gestion_horario')}?semana={(fecha - timedelta(days=fecha.weekday())).isoformat()}"

    def test_solo_entra_el_superadministrador(self):
        for usuario in (crear_usuario('laura', rol=Roles.ADMINISTRADOR), self.sofia, crear_usuario('ana')):
            self.client.force_login(usuario)
            with self.subTest(rol=usuario.rol):
                self.assertEqual(self.client.get(self.url('gestion_horario')).status_code, 403)

    def test_un_id_que_no_es_de_un_veterinario_responde_404(self):
        cliente = crear_usuario('ana')
        self.assertEqual(self.client.get(reverse('citas:gestion_horario', args=[cliente.pk])).status_code, 404)

    def test_ve_la_semana_del_veterinario_con_las_urls_de_la_gestion(self):
        bloque = crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        respuesta = self.client.get(self.url('gestion_horario'), {'semana': self.manana.isoformat()})
        self.assertEqual(respuesta.context['vet_gestionado'], self.sofia)
        self.assertContains(respuesta, 'Horario de Sofía Mora')
        self.assertContains(respuesta, self.url('gestion_horario_editar', bloque.pk))
        self.assertNotContains(respuesta, reverse('citas:horario_editar', args=[bloque.pk]))

    def test_agrega_un_bloque_al_veterinario_de_la_url(self):
        respuesta = self.client.post(self.url('gestion_horario'), {
            'fecha': self.manana.isoformat(), 'hora_inicio': '09:00', 'hora_fin': '12:00',
        })
        self.assertRedirects(respuesta, self.semana(self.manana))
        self.assertEqual(HorarioVeterinario.objects.get().veterinario, self.sofia)

    def test_revisa_los_cruces_con_los_bloques_del_veterinario(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        respuesta = self.client.post(self.url('gestion_horario'), {
            'fecha': self.manana.isoformat(), 'hora_inicio': '11:00', 'hora_fin': '13:00',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(HorarioVeterinario.objects.count(), 1)

    def test_edita_y_quita_un_bloque(self):
        bloque = crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        # "Cancelar" vuelve a la semana del bloque en la gestión, no a "Mi horario"
        self.assertContains(self.client.get(self.url('gestion_horario_editar', bloque.pk)), self.semana(self.manana))
        respuesta = self.client.post(self.url('gestion_horario_editar', bloque.pk), {
            'fecha': self.manana.isoformat(), 'hora_inicio': '10:00', 'hora_fin': '14:00',
        })
        self.assertRedirects(respuesta, self.semana(self.manana))
        bloque.refresh_from_db()
        self.assertEqual((bloque.hora_inicio, bloque.hora_fin), (time(10), time(14)))

        self.client.post(self.url('gestion_horario_eliminar', bloque.pk))
        self.assertFalse(HorarioVeterinario.objects.exists())

    def test_un_bloque_de_otro_veterinario_responde_404(self):
        ajeno = crear_horario(crear_veterinario('mateo'), time(9), time(12), fecha=self.manana)
        self.assertEqual(self.client.get(self.url('gestion_horario_editar', ajeno.pk)).status_code, 404)
        self.assertEqual(self.client.post(self.url('gestion_horario_eliminar', ajeno.pk)).status_code, 404)
        self.assertTrue(HorarioVeterinario.objects.filter(pk=ajeno.pk).exists())

    def test_copia_la_semana_anterior_del_veterinario(self):
        crear_horario(self.sofia, time(9), time(12), fecha=self.manana)
        siguiente = self.manana + timedelta(days=7)
        respuesta = self.client.post(self.url('gestion_horario_copiar'), {'semana': siguiente.isoformat()})
        self.assertRedirects(respuesta, self.semana(siguiente))
        self.assertTrue(HorarioVeterinario.objects.filter(veterinario=self.sofia, fecha=siguiente).exists())

    def test_elige_los_servicios_que_atiende(self):
        consulta = crear_servicio()
        vacuna = crear_servicio(nombre='Vacunación')
        respuesta = self.client.post(self.url('gestion_horario_servicios'), {'servicios': [consulta.pk, vacuna.pk]},
                                     follow=True)
        self.assertEqual(set(self.sofia.servicios.all()), {consulta, vacuna})
        self.assertContains(respuesta, 'Sofía Mora ahora atiende 2 servicios.')

    def test_la_grilla_de_horarios_enlaza_al_horario_solo_para_el_superadministrador(self):
        enlace = self.url('gestion_horario')
        self.assertContains(self.client.get(reverse('citas:gestion_horarios')), enlace)
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        self.assertNotContains(self.client.get(reverse('citas:gestion_horarios')), enlace)


class BloqueConCitasTests(TestCase):
    """RF-09: un bloque con citas confirmadas no se puede quitar; las atendidas, no asistió y canceladas
    no lo impiden. Sofía atiende mañana de 09:00 a 13:00 y Milo tiene una consulta a las 12:00."""

    def setUp(self):
        self.sofia = crear_veterinario()
        self.client.force_login(self.sofia)
        self.manana = timezone.localdate() + timedelta(days=1)
        self.bloque = crear_horario(self.sofia, time(9), time(13), fecha=self.manana)
        self.cita = Cita.objects.create(
            mascota=crear_mascota(crear_usuario('ana')), veterinario=self.sofia, servicio=crear_servicio(),
            inicio=self.hora(12), fin=self.hora(12, 30), precio=Decimal('25.00'),
        )

    def hora(self, horas, minutos=0):
        return timezone.make_aware(datetime.combine(self.manana, time(horas, minutos)))

    def quitar(self):
        return self.client.post(reverse('citas:horario_eliminar', args=[self.bloque.pk]), follow=True)

    def test_citas_dentro_solo_cuenta_las_confirmadas_del_bloque(self):
        # Una cita de otro día y otra de otro veterinario no son de este bloque
        Cita.objects.create(mascota=self.cita.mascota, veterinario=self.sofia, servicio=self.cita.servicio,
                            inicio=self.hora(12) + timedelta(days=1), fin=self.hora(12, 30) + timedelta(days=1),
                            precio=Decimal('25.00'))
        Cita.objects.create(mascota=self.cita.mascota, veterinario=crear_veterinario('mateo'),
                            servicio=self.cita.servicio, inicio=self.hora(10), fin=self.hora(10, 30),
                            precio=Decimal('25.00'))
        self.assertEqual(list(HorarioService.citas_dentro(self.bloque)), [self.cita])

    def test_quitar_bloque_con_una_cita_confirmada_lo_rechaza(self):
        aviso = 'Este bloque tiene 1 cita confirmada. Reprográmala o cancélala primero.'
        with self.assertRaisesMessage(ValidationError, aviso):
            HorarioService.quitar_bloque(self.bloque)
        self.assertTrue(HorarioVeterinario.objects.filter(pk=self.bloque.pk).exists())

    def test_borrar_desde_la_vista_deja_el_bloque_y_muestra_el_error(self):
        respuesta = self.quitar()
        self.assertTrue(HorarioVeterinario.objects.filter(pk=self.bloque.pk).exists())
        self.assertContains(respuesta, 'Este bloque tiene 1 cita confirmada.')
        self.assertNotContains(respuesta, 'Se quitó el bloque')

    def test_con_la_cita_cancelada_atendida_o_no_asistio_si_se_puede_quitar(self):
        for estado in (EstadoCita.CANCELADA, EstadoCita.ATENDIDA, EstadoCita.NO_ASISTIO):
            with self.subTest(estado=estado):
                Cita.objects.filter(pk=self.cita.pk).update(estado=estado)
                self.assertEqual(HorarioService.citas_dentro(self.bloque).count(), 0)
        self.assertContains(self.quitar(), 'Se quitó el bloque')
        self.assertFalse(HorarioVeterinario.objects.exists())

    def test_el_superadministrador_tampoco_puede_quitarlo(self):
        self.client.force_login(crear_usuario('sara', rol=Roles.SUPERADMIN))
        respuesta = self.client.post(reverse('citas:gestion_horario_eliminar', args=[self.sofia.pk, self.bloque.pk]),
                                     follow=True)
        self.assertTrue(HorarioVeterinario.objects.filter(pk=self.bloque.pk).exists())
        self.assertContains(respuesta, 'Este bloque tiene 1 cita confirmada.')

    def editar(self, inicio, fin, fecha=None):
        return self.client.post(reverse('citas:horario_editar', args=[self.bloque.pk]), {
            'fecha': (fecha or self.manana).isoformat(), 'hora_inicio': inicio, 'hora_fin': fin,
        })

    def assertBloqueIntacto(self):
        self.bloque.refresh_from_db()
        self.assertEqual((self.bloque.fecha, self.bloque.hora_inicio, self.bloque.hora_fin),
                         (self.manana, time(9), time(13)))

    def test_recortar_dejando_fuera_una_cita_confirmada_falla(self):
        respuesta = self.editar('09:00', '11:00')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Con este cambio, 1 cita confirmada quedaría fuera del bloque.')
        self.assertBloqueIntacto()

    def test_mover_el_bloque_a_otro_dia_falla(self):
        self.editar('09:00', '13:00', fecha=self.manana + timedelta(days=1))
        self.assertBloqueIntacto()

    def test_recortar_sin_dejar_fuera_la_cita_si_se_puede(self):
        self.editar('11:00', '12:30')
        self.bloque.refresh_from_db()
        self.assertEqual((self.bloque.hora_inicio, self.bloque.hora_fin), (time(11), time(12, 30)))

    def test_ampliar_el_bloque_si_se_puede(self):
        self.editar('08:00', '15:00')
        self.bloque.refresh_from_db()
        self.assertEqual((self.bloque.hora_inicio, self.bloque.hora_fin), (time(8), time(15)))

    def test_recortar_con_la_cita_cancelada_o_atendida_si_se_puede(self):
        for estado in (EstadoCita.CANCELADA, EstadoCita.ATENDIDA):
            with self.subTest(estado=estado):
                Cita.objects.filter(pk=self.cita.pk).update(estado=estado)
                HorarioVeterinario.objects.filter(pk=self.bloque.pk).update(hora_fin=time(13))
                self.editar('09:00', '11:00')
                self.bloque.refresh_from_db()
                self.assertEqual(self.bloque.hora_fin, time(11))

    def test_validar_cambio_cuenta_las_citas_que_quedan_fuera(self):
        with self.assertRaisesMessage(ValidationError, 'Reprográmala o cancélala primero.'):
            HorarioService.validar_cambio(self.bloque, self.manana, time(9), time(12, 15))
        HorarioService.validar_cambio(self.bloque, self.manana, time(12), time(12, 30))   # cabe justo


# ---------------------------------------------------------------------------
# Solo veterinarios verificados (RF-05, §2.1 paso a)
# ---------------------------------------------------------------------------
class VeterinarioVerificadoTests(TestCase):
    """Sofía está verificada; Mateo atiende el mismo servicio pero todavía no lo verificaron."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.servicio = crear_servicio()
        self.sofia = crear_veterinario('sofia')
        self.mateo = crear_veterinario('mateo', verificado=False)
        for veterinario in (self.sofia, self.mateo):
            self.servicio.veterinarios.add(veterinario)
            crear_horario(veterinario, time(9, 0), time(10, 0), fecha=self.fecha)
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.client.force_login(self.cliente)

    def inicio(self):
        return timezone.make_aware(datetime.combine(self.fecha, time(9, 0)))

    def veterinarios_con_turnos(self):
        return [veterinario for veterinario, _ in AgendaService.turnos_del_dia(self.servicio, self.fecha)]

    def test_el_no_verificado_no_aparece_en_los_turnos(self):
        self.assertEqual(self.veterinarios_con_turnos(), [self.sofia])
        respuesta = self.client.get(reverse('citas:turnos_del_dia'),
                                    {'servicio': self.servicio.pk, 'fecha': self.fecha.isoformat()})
        self.assertEqual([turno['veterinario'] for turno in respuesta.json()['turnos']], [self.sofia.pk])

    def test_sus_dias_no_se_marcan_en_el_calendario(self):
        otro_dia = self.fecha + timedelta(days=1)
        crear_horario(self.mateo, time(9, 0), time(10, 0), fecha=otro_dia)
        dias = AgendaService.dias_del_servicio(self.servicio, otro_dia.year, otro_dia.month)
        self.assertNotIn(otro_dia, dias)

    def test_no_se_puede_agendar_con_el_por_el_servicio(self):
        with self.assertRaises(ValidationError):
            AgendaService.agendar(mascota=self.mascota, veterinario=self.mateo, servicio=self.servicio,
                                  inicio=self.inicio())
        self.assertFalse(Cita.objects.exists())

    def test_no_se_puede_agendar_con_el_por_post(self):
        respuesta = self.client.post(reverse('citas:agendar'), {
            'mascota': self.mascota.pk, 'servicio': self.servicio.pk, 'veterinario': self.mateo.pk,
            'fecha': self.fecha.isoformat(), 'hora': '09:00',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('veterinario', respuesta.context['form'].errors)
        self.assertFalse(Cita.objects.exists())

    def test_al_verificarlo_aparece(self):
        PerfilVeterinario.objects.filter(usuario=self.mateo).update(verificado=True)
        self.assertEqual(set(self.veterinarios_con_turnos()), {self.sofia, self.mateo})
        cita = AgendaService.agendar(mascota=self.mascota, veterinario=self.mateo, servicio=self.servicio,
                                     inicio=self.inicio())
        self.assertEqual(cita.veterinario, self.mateo)

    def test_un_veterinario_sin_perfil_tampoco_aparece(self):
        nuevo = crear_usuario('lucia', rol=Roles.VETERINARIO)   # por ejemplo, recién le dieron el rol
        self.servicio.veterinarios.add(nuevo)
        crear_horario(nuevo, time(9, 0), time(10, 0), fecha=self.fecha)
        self.assertNotIn(nuevo, self.veterinarios_con_turnos())

    def test_un_servicio_que_solo_atiende_un_no_verificado_no_se_puede_agendar(self):
        solo_mateo = crear_servicio(nombre='Peluquería')
        solo_mateo.veterinarios.add(self.mateo)
        agendables = list(ServicioService.agendables())
        self.assertIn(self.servicio, agendables)
        self.assertNotIn(solo_mateo, agendables)

    def test_el_catalogo_solo_ofrece_casillas_de_verificados(self):
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        respuesta = self.client.get(reverse('citas:servicio_crear'))
        self.assertEqual(list(respuesta.context['form'].fields['veterinarios'].queryset), [self.sofia])
        respuesta = self.client.post(reverse('citas:servicio_crear'),
                                     datos_servicio(veterinarios=[self.mateo.pk]))
        self.assertIn('veterinarios', respuesta.context['form'].errors)

    def test_editar_el_servicio_no_le_quita_el_servicio_al_no_verificado(self):
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        self.client.post(reverse('citas:servicio_editar', args=[self.servicio.pk]),
                         datos_servicio(nombre='Consulta general', veterinarios=[self.sofia.pk]))
        self.assertEqual(set(self.servicio.veterinarios.all()), {self.sofia, self.mateo})


# ---------------------------------------------------------------------------
# F7: calificar la atención (RF-21, RF-22)
# ---------------------------------------------------------------------------
def crear_cita_pasada(mascota, veterinario, servicio, estado=EstadoCita.ATENDIDA, dias=1):
    """Una cita de hace unos días, ya cerrada con ese estado."""
    inicio = timezone.now() - timedelta(days=dias)
    return Cita.objects.create(mascota=mascota, veterinario=veterinario, servicio=servicio, inicio=inicio,
                               fin=inicio + timedelta(minutes=servicio.duracion_min), precio=servicio.precio,
                               estado=estado)


class CalificarServiceTests(TestCase):
    """AgendaService.calificar() y la reputación del veterinario."""

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.cita = crear_cita_pasada(self.mascota, self.veterinario, self.servicio)

    def test_califica_una_cita_atendida(self):
        calificacion = AgendaService.calificar(self.cita, self.cliente, 5, '  Muy amable  ')
        self.assertEqual((calificacion.estrellas, calificacion.comentario), (5, 'Muy amable'))
        self.assertFalse(CalificacionService.puede_calificar(self.cita))

    def test_calificar_dos_veces_se_rechaza(self):
        AgendaService.calificar(self.cita, self.cliente, 4)
        with self.assertRaises(ValidationError):
            AgendaService.calificar(self.cita, self.cliente, 2)
        self.assertEqual(Calificacion.objects.get().estrellas, 4)

    def test_la_base_tambien_rechaza_una_segunda_calificacion(self):
        Calificacion.objects.create(cita=self.cita, estrellas=4)
        with self.assertRaises(IntegrityError):
            Calificacion.objects.create(cita=self.cita, estrellas=2)

    def test_una_cita_confirmada_cancelada_o_no_asistida_no_se_califica(self):
        for dias, estado in enumerate((EstadoCita.CONFIRMADA, EstadoCita.CANCELADA, EstadoCita.NO_ASISTIO), 2):
            with self.subTest(estado=estado):
                cita = crear_cita_pasada(self.mascota, self.veterinario, self.servicio, estado=estado, dias=dias)
                self.assertFalse(CalificacionService.puede_calificar(cita))
                with self.assertRaises(ValidationError):
                    AgendaService.calificar(cita, self.cliente, 5)
        self.assertFalse(Calificacion.objects.exists())

    def test_no_se_califica_la_cita_de_otro_cliente(self):
        with self.assertRaises(ValidationError):
            AgendaService.calificar(self.cita, crear_usuario('luis'), 5)

    def test_las_estrellas_van_de_1_a_5(self):
        for estrellas in (0, 6):
            with self.subTest(estrellas=estrellas), self.assertRaises(ValidationError):
                AgendaService.calificar(self.cita, self.cliente, estrellas)
        with self.assertRaises(IntegrityError):
            Calificacion.objects.create(cita=self.cita, estrellas=6)

    def test_el_promedio_y_la_distribucion_se_calculan_bien(self):
        for dias, estrellas in ((1, 5), (2, 4), (3, 4), (4, 2)):
            cita = self.cita if dias == 1 else crear_cita_pasada(self.mascota, self.veterinario, self.servicio,
                                                                 dias=dias)
            AgendaService.calificar(cita, self.cliente, estrellas)
        resumen = CalificacionService.resumen_del_veterinario(self.veterinario)
        self.assertEqual(resumen['promedio'], 3.8)   # (5 + 4 + 4 + 2) / 4 = 3.75
        self.assertEqual(resumen['total'], 4)
        self.assertEqual([fila['cantidad'] for fila in resumen['distribucion']], [1, 2, 0, 1, 0])
        self.assertEqual(resumen['distribucion'][1]['porcentaje'], 50)
        self.assertEqual(CalificacionService.promedio_dado_por(self.cliente), 3.8)

    def test_sin_opiniones_no_hay_promedio(self):
        resumen = CalificacionService.resumen_del_veterinario(self.veterinario)
        self.assertIsNone(resumen['promedio'])
        self.assertEqual(resumen['total'], 0)
        self.assertIsNone(CalificacionService.promedio_dado_por(self.cliente))


class CalificarVistaTests(TestCase):
    """La página Calificar la atención (/citas/mis-citas/<pk>/calificar/)."""

    def setUp(self):
        self.veterinario = crear_veterinario(first_name='Valeria', last_name='Ruiz')
        self.servicio = crear_servicio()
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.cita = crear_cita_pasada(self.mascota, self.veterinario, self.servicio)
        self.url = reverse('citas:calificar', args=[self.cita.pk])
        self.client.force_login(self.cliente)

    def test_muestra_la_cita_y_al_veterinario(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '¿Cómo fue la atención de Valeria Ruiz?')
        self.assertContains(respuesta, 'name="estrellas"', count=5)

    def test_calificar_guarda_y_vuelve_a_mis_citas(self):
        respuesta = self.client.post(self.url, {'estrellas': '4', 'comentario': 'Explicó todo muy bien'})
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        calificacion = Calificacion.objects.get(cita=self.cita)
        self.assertEqual((calificacion.estrellas, calificacion.comentario), (4, 'Explicó todo muy bien'))

    def test_la_cita_de_otro_cliente_responde_404(self):
        self.client.force_login(crear_usuario('luis'))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'estrellas': '1'}).status_code, 404)
        self.assertFalse(Calificacion.objects.exists())

    def test_solo_el_cliente_entra(self):
        self.client.force_login(self.veterinario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_calificar_dos_veces_se_rechaza(self):
        self.client.post(self.url, {'estrellas': '5'})
        respuesta = self.client.post(self.url, {'estrellas': '1'})
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        self.assertEqual(Calificacion.objects.get().estrellas, 5)

    def test_una_cita_confirmada_no_se_califica(self):
        self.cita.estado = EstadoCita.CONFIRMADA
        self.cita.save(update_fields=['estado'])
        self.assertRedirects(self.client.get(self.url), reverse('citas:mis_citas'))
        self.client.post(self.url, {'estrellas': '5'})
        self.assertFalse(Calificacion.objects.exists())

    def test_sin_estrellas_o_fuera_de_rango_muestra_el_error(self):
        for datos in ({}, {'estrellas': '9'}):
            with self.subTest(datos=datos):
                respuesta = self.client.post(self.url, datos)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn('estrellas', respuesta.context['form'].errors)
        self.assertFalse(Calificacion.objects.exists())


class PerfilVeterinarioVistaTests(TestCase):
    """El perfil del veterinario (/citas/veterinarios/<pk>/): especialidad, promedio y opiniones."""

    def setUp(self):
        self.veterinario = crear_veterinario(first_name='Valeria', last_name='Ruiz')
        PerfilVeterinario.objects.filter(usuario=self.veterinario).update(especialidad='Cirugía', anios_experiencia=8)
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        self.cliente = crear_usuario('ana', first_name='Carlos', last_name='Mena')
        self.mascota = crear_mascota(self.cliente)
        self.url = reverse('citas:perfil_veterinario', args=[self.veterinario.pk])
        self.client.force_login(self.cliente)

    def calificar(self, estrellas, comentario='', dias=1):
        cita = crear_cita_pasada(self.mascota, self.veterinario, self.servicio, dias=dias)
        return AgendaService.calificar(cita, self.cliente, estrellas, comentario)

    def test_muestra_especialidad_promedio_y_opiniones(self):
        self.calificar(5, 'Excelente trato', dias=1)
        self.calificar(4, dias=2)
        self.client.force_login(crear_usuario('luis'))   # otro cliente mira el perfil antes de agendar
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Cirugía · 8 años de experiencia')
        self.assertContains(respuesta, 'Consulta general')
        self.assertEqual(respuesta.context['reputacion']['promedio'], 4.5)
        self.assertContains(respuesta, '2 opiniones')
        self.assertContains(respuesta, 'Excelente trato')
        self.assertContains(respuesta, 'Carlos M.')
        self.assertNotContains(respuesta, 'Mena')   # del dueño solo se ve la inicial del apellido

    def test_sin_opiniones_lo_dice(self):
        self.assertContains(self.client.get(self.url), 'Todavía nadie lo ha calificado.')

    def test_un_id_que_no_es_de_un_veterinario_responde_404(self):
        self.assertEqual(self.client.get(reverse('citas:perfil_veterinario', args=[self.cliente.pk])).status_code, 404)

    def test_pide_iniciar_sesion(self):
        self.client.logout()
        self.assertIn(reverse('cuentas:login'), self.client.get(self.url).url)


class CalificacionEnMisCitasTests(TestCase):
    """Mis citas: el botón Calificar, el promedio que dio el cliente y los enlaces al perfil del doctor."""

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        self.cliente = crear_usuario('ana')
        self.mascota = crear_mascota(self.cliente)
        self.atendida = crear_cita_pasada(self.mascota, self.veterinario, self.servicio, dias=1)
        self.client.force_login(self.cliente)

    def pasadas(self):
        return self.client.get(reverse('citas:mis_citas'), {'vista': 'pasadas'})

    def test_una_atendida_sin_calificar_muestra_el_boton(self):
        self.assertContains(self.pasadas(), reverse('citas:calificar', args=[self.atendida.pk]))

    def test_calificar_se_abre_en_un_pop_up_en_mis_citas(self):
        # El botón lleva los datos para el pop-up; el enlace sigue sirviendo sin JavaScript
        respuesta = self.pasadas()
        self.assertContains(respuesta, 'data-dialogo-calificar')
        self.assertContains(respuesta, 'data-calificar')
        self.assertContains(respuesta, 'value="5" data-texto="Excelente"')

    def test_el_pop_up_envia_al_mismo_post_y_vuelve_a_mis_citas(self):
        respuesta = self.client.post(reverse('citas:calificar', args=[self.atendida.pk]), {'estrellas': '5'})
        self.assertRedirects(respuesta, reverse('citas:mis_citas'))
        self.assertEqual(self.atendida.calificacion.estrellas, 5)

    def test_una_ya_calificada_muestra_sus_estrellas_y_no_el_boton(self):
        AgendaService.calificar(self.atendida, self.cliente, 4)
        respuesta = self.pasadas()
        self.assertNotContains(respuesta, reverse('citas:calificar', args=[self.atendida.pk]))
        self.assertContains(respuesta, 'La calificaste con 4 de 5 estrellas')

    def test_una_no_asistida_no_se_puede_calificar(self):
        no_asistio = crear_cita_pasada(self.mascota, self.veterinario, self.servicio,
                                       estado=EstadoCita.NO_ASISTIO, dias=2)
        self.assertNotContains(self.pasadas(), reverse('citas:calificar', args=[no_asistio.pk]))

    def test_muestra_la_calificacion_promedio_que_dio(self):
        self.assertIsNone(self.pasadas().context['promedio_dado'])
        AgendaService.calificar(self.atendida, self.cliente, 5)
        AgendaService.calificar(crear_cita_pasada(self.mascota, self.veterinario, self.servicio, dias=3),
                                self.cliente, 4)
        respuesta = self.pasadas()
        self.assertEqual(respuesta.context['promedio_dado'], 4.5)
        self.assertContains(respuesta, 'Tu calificación promedio')

    def test_el_doctor_de_la_tarjeta_enlaza_a_su_perfil(self):
        self.assertContains(self.pasadas(), reverse('citas:perfil_veterinario', args=[self.veterinario.pk]))

    def test_los_turnos_de_agendar_traen_el_perfil_del_doctor(self):
        fecha = timezone.localdate() + timedelta(days=7)
        crear_horario(self.veterinario, time(9, 0), time(10, 0), fecha=fecha)
        respuesta = self.client.get(reverse('citas:turnos_del_dia'),
                                    {'servicio': self.servicio.pk, 'fecha': fecha.isoformat()})
        self.assertEqual(respuesta.json()['turnos'][0]['perfil'],
                         reverse('citas:perfil_veterinario', args=[self.veterinario.pk]))


# ---------------------------------------------------------------------------
# F8: avisos por correo y recordatorio de 24 h (RF-23, RF-24)
# ---------------------------------------------------------------------------
class AvisosDeCitasTests(TestCase):
    """Agendar, reprogramar y cancelar avisan al cliente y al veterinario, y solo si el cambio se guardó."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario(first_name='Sofía', last_name='Paredes', email='sofia@woof.ec')
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.cliente = crear_usuario('ana', first_name='Ana', email='ana@correo.ec')
        self.mascota = crear_mascota(self.cliente)
        self.client.force_login(self.cliente)

    def agendar(self, hora='09:30'):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('citas:agendar'), {
                'mascota': self.mascota.pk, 'servicio': self.servicio.pk, 'veterinario': self.veterinario.pk,
                'fecha': self.fecha.isoformat(), 'hora': hora, 'motivo': 'Control',
            })
        return Cita.objects.get()

    @override_settings(AVISOS_EN_SEGUNDO_PLANO=True)
    def test_en_produccion_el_correo_sale_en_otro_hilo_y_la_reserva_no_espera(self):
        with patch('citas.services.notificaciones.threading.Thread') as hilo:
            self.agendar()   # agendar() ya ejecuta los avisos de on_commit
        self.assertEqual(hilo.call_count, 2)                   # un hilo por aviso (cliente y veterinario)
        self.assertEqual(hilo.return_value.start.call_count, 2)
        self.assertEqual(len(mail.outbox), 0)                  # nada se envió mientras respondía la reserva
        self.assertEqual(Notificacion.objects.count(), 2)      # la campana ya los tiene

    def test_agendar_manda_dos_correos_y_guarda_dos_avisos(self):
        cita = self.agendar()
        self.assertEqual(sorted(correo.to[0] for correo in mail.outbox), ['ana@correo.ec', 'sofia@woof.ec'])
        self.assertEqual(mail.outbox[0].subject, 'Woof · Cita agendada')
        self.assertIn('quedó confirmada', mail.outbox[0].body)
        self.assertEqual(Notificacion.objects.filter(cita=cita, tipo=TipoNotificacion.AGENDADA).count(), 2)

    def test_los_avisos_se_envian_solo_al_confirmar_la_transaccion(self):
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            self.client.post(reverse('citas:agendar'), {
                'mascota': self.mascota.pk, 'servicio': self.servicio.pk, 'veterinario': self.veterinario.pk,
                'fecha': self.fecha.isoformat(), 'hora': '09:30',
            })
        self.assertEqual(len(pendientes), 1)       # esperan al commit
        self.assertEqual(len(mail.outbox), 0)      # si la transacción se deshace, no salen

    def test_un_turno_ocupado_no_avisa_a_nadie(self):
        self.agendar()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('citas:agendar'), {
                'mascota': self.mascota.pk, 'servicio': self.servicio.pk, 'veterinario': self.veterinario.pk,
                'fecha': self.fecha.isoformat(), 'hora': '09:30',
            })
        self.assertEqual(len(mail.outbox), 0)

    def test_reprogramar_avisa_con_la_hora_anterior(self):
        cita = self.agendar('09:00')
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('citas:reprogramar', args=[cita.pk]),
                             {'fecha': self.fecha.isoformat(), 'hora': '10:00'})
        self.assertEqual(len(mail.outbox), 2)
        aviso = Notificacion.objects.get(usuario=self.cliente, tipo=TipoNotificacion.REPROGRAMADA)
        self.assertIn('a las 09:00', aviso.mensaje)
        self.assertIn('a las 10:00', aviso.mensaje)

    def test_el_cliente_cancela_y_el_veterinario_sabe_quien_fue(self):
        cita = self.agendar()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('citas:cancelar', args=[cita.pk]))
        aviso = Notificacion.objects.get(usuario=self.veterinario, tipo=TipoNotificacion.CANCELADA)
        self.assertIn('Ana', aviso.mensaje)
        self.assertIn('canceló', aviso.mensaje)

    def test_la_clinica_cancela_con_motivo(self):
        cita = self.agendar()
        self.client.force_login(crear_usuario('laura', rol=Roles.ADMINISTRADOR))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('citas:gestion_cancelar', args=[cita.pk]),
                             {'motivo': 'La doctora tiene una emergencia'})
        aviso = Notificacion.objects.get(usuario=self.cliente, tipo=TipoNotificacion.CANCELADA)
        self.assertIn('La clínica canceló', aviso.mensaje)
        self.assertIn('Motivo: La doctora tiene una emergencia.', aviso.mensaje)

    def test_si_el_correo_falla_la_cita_y_el_aviso_quedan(self):
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('SMTP caído')), \
                self.assertLogs('citas.models.notificacion', level='ERROR'):
            cita = self.agendar()
        self.assertEqual(cita.estado, EstadoCita.CONFIRMADA)
        self.assertEqual(Notificacion.objects.count(), 2)

    @override_settings(CORREO_AVISOS=False)
    def test_con_los_correos_apagados_solo_se_guardan_los_avisos(self):
        self.agendar()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notificacion.objects.count(), 2)


class RecordatoriosTests(TestCase):
    """python manage.py enviar_recordatorios: citas confirmadas que empiezan en 23 a 25 horas."""

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.cliente = crear_usuario('ana', email='ana@correo.ec')
        self.mascota = crear_mascota(self.cliente)

    def cita_en(self, horas, estado=EstadoCita.CONFIRMADA):
        inicio = timezone.now() + timedelta(hours=horas)
        return Cita.objects.create(mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
                                   inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'),
                                   estado=estado)

    def ejecutar(self):
        salida = StringIO()
        call_command('enviar_recordatorios', stdout=salida)
        return salida.getvalue()

    def test_recuerda_la_cita_de_manana_solo_al_cliente(self):
        cita = self.cita_en(24)
        self.assertIn('Se enviaron 1 recordatorio.', self.ejecutar())
        self.assertEqual([correo.to for correo in mail.outbox], [['ana@correo.ec']])
        self.assertTrue(Notificacion.objects.filter(cita=cita, tipo=TipoNotificacion.RECORDATORIO).exists())

    def test_no_envia_dos_veces_el_mismo_recordatorio(self):
        self.cita_en(24)
        self.ejecutar()
        self.assertIn('Se enviaron 0 recordatorios.', self.ejecutar())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Notificacion.objects.filter(tipo=TipoNotificacion.RECORDATORIO).count(), 1)

    def test_una_cita_cancelada_no_recibe_recordatorio(self):
        self.cita_en(24, estado=EstadoCita.CANCELADA)
        self.ejecutar()
        self.assertEqual(len(mail.outbox), 0)

    def test_fuera_de_la_ventana_no_se_recuerda(self):
        self.cita_en(5)
        self.cita_en(48)
        self.ejecutar()
        self.assertEqual(len(mail.outbox), 0)

    def test_la_base_no_acepta_dos_recordatorios_de_la_misma_cita(self):
        cita = self.cita_en(24)
        NotificacionService.recordatorio(cita)
        self.assertIsNone(NotificacionService.recordatorio(cita))
        with self.assertRaises(IntegrityError):
            Notificacion.objects.create(usuario=self.cliente, cita=cita, tipo=TipoNotificacion.RECORDATORIO,
                                        mensaje='otra vez')


class CampanaTests(TestCase):
    """La campana del panel: el número de avisos sin leer y la página que los muestra."""

    def setUp(self):
        self.cliente = crear_usuario('ana')
        for mensaje in ('Primero', 'Segundo'):
            Notificacion.objects.create(usuario=self.cliente, tipo=TipoNotificacion.AGENDADA, mensaje=mensaje)
        Notificacion.objects.create(usuario=crear_usuario('luis'), tipo=TipoNotificacion.AGENDADA, mensaje='Ajeno')
        self.client.force_login(self.cliente)

    def test_la_campana_muestra_cuantos_avisos_no_ha_leido(self):
        respuesta = self.client.get(reverse('citas:mis_citas'))
        self.assertEqual(respuesta.context['notificaciones_sin_leer'], 2)
        self.assertContains(respuesta, 'Notificaciones: 2 sin leer')

    def test_abrir_los_avisos_los_marca_como_leidos(self):
        respuesta = self.client.get(reverse('citas:notificaciones'))
        self.assertContains(respuesta, 'Primero')
        self.assertNotContains(respuesta, 'Ajeno')     # solo los suyos
        self.assertContains(respuesta, 'Nuevo', count=2)
        self.assertEqual(NotificacionService.no_leidas(self.cliente), 0)
        self.assertNotContains(self.client.get(reverse('citas:notificaciones')), 'Nuevo')

    def test_pide_iniciar_sesion(self):
        self.client.logout()
        self.assertIn(reverse('cuentas:login'), self.client.get(reverse('citas:notificaciones')).url)


class FiltroPorMascotaTests(TestCase):
    """RF-15: Mis citas se filtra por una de las mascotas del cliente con ?mascota=<id>."""

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.cliente = crear_usuario('ana')
        self.milo = crear_mascota(self.cliente, nombre='Milo')
        self.luna = crear_mascota(self.cliente, nombre='Luna', especie='gato')
        self.cita_milo = self.agendar(self.milo, 9)
        self.cita_luna = self.agendar(self.luna, 10)
        self.client.force_login(self.cliente)

    def agendar(self, mascota, horas, minutos=0):
        inicio = timezone.make_aware(datetime.combine(self.fecha, time(horas, minutos)))
        return AgendaService.agendar(mascota=mascota, veterinario=self.veterinario, servicio=self.servicio,
                                     inicio=inicio)

    def mis_citas(self, **parametros):
        return self.client.get(reverse('citas:mis_citas'), parametros)

    def citas_mostradas(self, respuesta):
        return [cita for _, citas in respuesta.context['por_dia'] for cita in citas]

    def test_sin_filtro_muestra_las_citas_de_todas_sus_mascotas(self):
        respuesta = self.mis_citas()
        self.assertEqual(self.citas_mostradas(respuesta), [self.cita_milo, self.cita_luna])
        self.assertIsNone(respuesta.context['mascota_elegida'])

    def test_con_una_mascota_muestra_solo_sus_citas(self):
        respuesta = self.mis_citas(mascota=self.luna.pk)
        self.assertEqual(self.citas_mostradas(respuesta), [self.cita_luna])
        self.assertEqual(respuesta.context['mascota_elegida'], self.luna)
        # La cantidad de la pestaña Próximas también cuenta solo las de Luna
        self.assertIn(('proximas', 'Próximas', 1), respuesta.context['pestanas'])

    def test_el_filtro_se_combina_con_la_pestana(self):
        AgendaService.cancelar(self.cita_milo)
        respuesta = self.mis_citas(vista='canceladas', mascota=self.milo.pk)
        self.assertEqual(self.citas_mostradas(respuesta), [self.cita_milo])
        self.assertEqual(self.citas_mostradas(self.mis_citas(vista='canceladas', mascota=self.luna.pk)), [])

    def test_las_pestanas_conservan_la_mascota_elegida(self):
        self.assertContains(self.mis_citas(mascota=self.milo.pk), f'?vista=pasadas&amp;mascota={self.milo.pk}')

    def test_la_mascota_de_otro_cliente_no_filtra_ni_muestra_sus_citas(self):
        otra = crear_mascota(crear_usuario('luis'), nombre='Toby')
        self.agendar(otra, 10, 30)
        respuesta = self.mis_citas(mascota=otra.pk)
        # El id ajeno se ignora: se ven las citas propias (todas) y nada de Toby
        self.assertIsNone(respuesta.context['mascota_elegida'])
        self.assertEqual(self.citas_mostradas(respuesta), [self.cita_milo, self.cita_luna])
        self.assertNotContains(respuesta, 'Toby')

    def test_un_id_inventado_se_ignora(self):
        for valor in ('abc', '99999', ''):
            with self.subTest(valor=valor):
                respuesta = self.mis_citas(mascota=valor)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIsNone(respuesta.context['mascota_elegida'])

    def test_con_una_sola_mascota_no_se_muestran_los_chips(self):
        self.luna.delete()
        self.assertNotContains(self.mis_citas(), 'Filtrar por mascota')

    def test_con_varias_mascotas_se_muestran_los_chips(self):
        self.assertContains(self.mis_citas(), 'Filtrar por mascota')


class IndicadoresTests(TestCase):
    """
    RF-25 y §2.5: el ejemplo del documento. El martes 13/10/2026 la Dra. Paredes tiene el bloque 09:00-13:00
    (240 min) y las citas de Luna (30), Kira (30), Simba (20) y Toby (30, cancelada): 80 ÷ 240 = 33,3 %.
    """
    FECHA = date(2026, 10, 13)

    def setUp(self):
        self.paredes = crear_veterinario('paredes', first_name='Sofía', last_name='Paredes')
        self.consulta = crear_servicio()
        self.desparasitacion = crear_servicio(nombre='Desparasitación', duracion_min=20, precio=Decimal('15.00'))
        crear_horario(self.paredes, time(9, 0), time(13, 0), fecha=self.FECHA)
        dueno = crear_usuario('ana')
        self.luna = self.cita('Luna', dueno, 9, 30, estado=EstadoCita.ATENDIDA)
        self.kira = self.cita('Kira', dueno, 10, 0, estado=EstadoCita.NO_ASISTIO)
        self.simba = self.cita('Simba', dueno, 12, 0, servicio=self.desparasitacion)
        self.toby = self.cita('Toby', dueno, 11, 0, estado=EstadoCita.CANCELADA)
        self.admin = crear_usuario('laura', rol=Roles.ADMINISTRADOR)
        self.client.force_login(self.admin)
        self.url = reverse('citas:indicadores')

    def cita(self, nombre, dueno, horas, minutos, servicio=None, estado=EstadoCita.CONFIRMADA, veterinario=None):
        servicio = servicio or self.consulta
        inicio = timezone.make_aware(datetime.combine(self.FECHA, time(horas, minutos)))
        return Cita.objects.create(mascota=crear_mascota(dueno, nombre=nombre), veterinario=veterinario or self.paredes,
                                   servicio=servicio, inicio=inicio, fin=inicio + timedelta(minutes=servicio.duracion_min),
                                   precio=servicio.precio, estado=estado)

    def indicadores(self, veterinario=None):
        return EstadisticasService.indicadores(self.FECHA, self.FECHA, veterinario)

    # ---------- El service ----------
    def test_la_ocupacion_del_ejemplo_es_33_3(self):
        fila = self.indicadores()['filas'][0]
        self.assertEqual((fila['minutos_citas'], fila['minutos_horario']), (80, 240))
        self.assertEqual(fila['ocupacion'], 33.3)

    def test_con_la_cita_de_ana_sube_a_45_8(self):
        self.cita('Milo', crear_usuario('ana2'), 10, 30)
        self.assertEqual(self.indicadores()['filas'][0]['ocupacion'], 45.8)
        self.assertEqual(self.indicadores()['ocupacion'], 45.8)

    def test_cuenta_las_citas_por_estado(self):
        por_estado = {valor: cantidad for valor, _, cantidad in self.indicadores()['por_estado']}
        self.assertEqual(por_estado, {EstadoCita.CONFIRMADA: 1, EstadoCita.ATENDIDA: 1,
                                      EstadoCita.NO_ASISTIO: 1, EstadoCita.CANCELADA: 1})
        fila = self.indicadores()['filas'][0]
        self.assertEqual((fila['citas'], fila['canceladas']), (3, 1))

    def test_los_ingresos_son_solo_de_las_atendidas(self):
        self.assertEqual(self.indicadores()['ingresos'], Decimal('25.00'))  # Luna; Kira no asistió, Toby se canceló

    def test_filtra_por_veterinario(self):
        leon = crear_veterinario('leon', first_name='Mateo', last_name='León')
        crear_horario(leon, time(9, 0), time(11, 0), fecha=self.FECHA)
        self.cita('Rocky', crear_usuario('carlos'), 9, 0, veterinario=leon, estado=EstadoCita.ATENDIDA)
        todos = self.indicadores()
        self.assertEqual([fila['veterinario'] for fila in todos['filas']], [leon, self.paredes])
        # Clínica: (30 + 80) ÷ (120 + 240) = 30,6 %
        self.assertEqual(todos['ocupacion'], 30.6)
        solo_leon = self.indicadores(leon)
        self.assertEqual([fila['veterinario'] for fila in solo_leon['filas']], [leon])
        self.assertEqual(solo_leon['ocupacion'], 25.0)
        self.assertEqual(solo_leon['total_citas'], 1)

    def test_fuera_del_rango_no_cuenta(self):
        otro_dia = EstadisticasService.indicadores(self.FECHA + timedelta(days=1), self.FECHA + timedelta(days=7))
        self.assertEqual((otro_dia['total_citas'], otro_dia['filas'], otro_dia['ocupacion']), (0, [], 0))

    def test_sin_horario_la_ocupacion_es_cero_y_la_barra_no_pasa_de_100(self):
        HorarioVeterinario.objects.all().delete()
        fila = self.indicadores()['filas'][0]
        self.assertEqual((fila['ocupacion'], fila['barra']), (0, 0))

    # ---------- La vista ----------
    def test_solo_la_abre_la_gestion_de_la_clinica(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for usuario in (self.paredes, crear_usuario('cliente')):
            self.client.force_login(usuario)
            with self.subTest(rol=usuario.rol):
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_muestra_la_ocupacion_y_los_ingresos_del_rango(self):
        respuesta = self.client.get(self.url, {'desde': '2026-10-13', 'hasta': '2026-10-13'})
        self.assertContains(respuesta, 'Sofía Paredes')
        self.assertContains(respuesta, '33,3 %')
        self.assertContains(respuesta, '$25,00')

    def test_filtra_por_veterinario_en_la_vista(self):
        leon = crear_veterinario('leon', first_name='Mateo', last_name='León')
        respuesta = self.client.get(self.url, {'desde': '2026-10-13', 'hasta': '2026-10-13', 'veterinario': leon.pk})
        self.assertEqual(respuesta.context['veterinario'], leon)
        # Paredes sigue en el desplegable, pero no en el reporte
        self.assertEqual(respuesta.context['filas'], [])
        self.assertEqual(respuesta.context['total_citas'], 0)

    def test_sin_parametros_muestra_los_ultimos_30_dias(self):
        respuesta = self.client.get(self.url)
        hoy = timezone.localdate()
        self.assertEqual((respuesta.context['desde'], respuesta.context['hasta']), (hoy - timedelta(days=29), hoy))

    def test_un_rango_al_reves_avisa_y_vuelve_a_30_dias(self):
        respuesta = self.client.get(self.url, {'desde': '2026-10-20', 'hasta': '2026-10-13'})
        self.assertContains(respuesta, 'debe ser anterior o igual')
        self.assertEqual(respuesta.context['hasta'], timezone.localdate())

    def test_un_rango_de_mas_de_un_ano_no_se_acepta(self):
        respuesta = self.client.get(self.url, {'desde': '2025-01-01', 'hasta': '2026-10-13'})
        self.assertContains(respuesta, 'un año como máximo')


class EjemploDelDocumentoTests(TestCase):
    """
    Casos del plan de pruebas (§3.5) con el ejemplo del §2.1: la Dra. Paredes atiende de 09:00 a 13:00 y ya tiene
    a Luna (09:30), Kira (10:00), Simba (12:00, desparasitación de 20 min) y a Toby (11:00, cancelada).
    """

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.paredes = crear_veterinario('paredes')
        self.consulta = crear_servicio()
        self.desparasitacion = crear_servicio(nombre='Desparasitación', duracion_min=20, precio=Decimal('15.00'))
        self.consulta.veterinarios.add(self.paredes)
        crear_horario(self.paredes, time(9, 0), time(13, 0), fecha=self.fecha)
        self.dueno = crear_usuario('ana')
        for nombre, horas, minutos, servicio, estado in (
            ('Luna', 9, 30, self.consulta, EstadoCita.CONFIRMADA),
            ('Kira', 10, 0, self.consulta, EstadoCita.CONFIRMADA),
            ('Simba', 12, 0, self.desparasitacion, EstadoCita.CONFIRMADA),
            ('Toby', 11, 0, self.consulta, EstadoCita.CANCELADA),
        ):
            inicio = self.hora(horas, minutos)
            Cita.objects.create(mascota=crear_mascota(self.dueno, nombre=nombre), veterinario=self.paredes,
                                servicio=servicio, inicio=inicio, fin=inicio + timedelta(minutes=servicio.duracion_min),
                                precio=servicio.precio, estado=estado)

    def hora(self, horas, minutos=0):
        return timezone.make_aware(datetime.combine(self.fecha, time(horas, minutos)))

    def test_espacios_libres_del_ejemplo(self):
        # Figura 1: Ana ve 09:00, 10:30, 11:00, 11:30 y 12:30
        espacios = AgendaService.espacios_disponibles(self.paredes, self.consulta, self.fecha)
        self.assertEqual(espacios, [self.hora(9), self.hora(10, 30), self.hora(11), self.hora(11, 30),
                                    self.hora(12, 30)])

    def test_dos_citas_que_solo_se_tocan_no_se_cruzan(self):
        # 09:00-09:30 termina justo cuando empieza Luna (09:30-10:00): no comparten ningún minuto
        milo = AgendaService.agendar(mascota=crear_mascota(self.dueno, nombre='Milo'), veterinario=self.paredes,
                                     servicio=self.consulta, inicio=self.hora(9))
        self.assertEqual((milo.fin, milo.estado), (self.hora(9, 30), EstadoCita.CONFIRMADA))

    def test_la_cita_cancelada_deja_su_turno_libre(self):
        self.assertIn(self.hora(11), AgendaService.espacios_disponibles(self.paredes, self.consulta, self.fecha))

    def test_cancelar_una_cita_que_ya_empezo_se_rechaza(self):
        empezada = Cita.objects.create(
            mascota=crear_mascota(self.dueno, nombre='Rocky'), veterinario=self.paredes, servicio=self.consulta,
            inicio=timezone.now() - timedelta(minutes=10), fin=timezone.now() + timedelta(minutes=20),
            precio=Decimal('25.00'),
        )
        with self.assertRaisesMessage(ValidationError, 'ya empezó'):
            AgendaService.cancelar(empezada)
        empezada.refresh_from_db()
        self.assertEqual(empezada.estado, EstadoCita.CONFIRMADA)


@skipUnless(connection.vendor == 'postgresql', 'select_for_update solo bloquea de verdad en PostgreSQL (CI y Neon)')
class ReservasSimultaneasTests(TransactionTestCase):
    """
    §3.5: dos reservas del mismo turno llegan al mismo tiempo, cada una en su propio hilo y su propia conexión.
    El bloqueo del veterinario (select_for_update) las ordena: solo se crea una cita y la otra recibe el aviso.
    Para que de verdad se crucen, la revisión de turnos libres se hace más lenta mientras dura la prueba.
    """
    serialized_rollback = True   # al terminar se restauran los datos de las migraciones (especies, vacunas...)

    def setUp(self):
        self.fecha = timezone.localdate() + timedelta(days=7)
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.servicio.veterinarios.add(self.veterinario)
        crear_horario(self.veterinario, time(9, 0), time(11, 0), fecha=self.fecha)
        self.milo = crear_mascota(crear_usuario('ana'), nombre='Milo')
        self.rocky = crear_mascota(crear_usuario('carlos'), nombre='Rocky')

    def hora(self, horas, minutos=0):
        return timezone.make_aware(datetime.combine(self.fecha, time(horas, minutos)))

    def a_la_vez(self, *acciones):
        """Corre cada acción en su hilo, todas a la vez (Barrier). Devuelve lo que devolvió cada una o su error."""
        barrera = threading.Barrier(len(acciones))
        resultados = [None] * len(acciones)
        original = AgendaService.espacios_disponibles

        def lento(*args, **kwargs):
            espacios = original(*args, **kwargs)
            time_module.sleep(0.3)   # da tiempo a que la otra reserva llegue mientras esta revisa
            return espacios

        def correr(indice, accion):
            try:
                barrera.wait()
                resultados[indice] = accion()
            except ValidationError as error:
                resultados[indice] = error
            finally:
                connection.close()   # cada hilo abrió su propia conexión

        with patch.object(AgendaService, 'espacios_disponibles', side_effect=lento):
            hilos = [threading.Thread(target=correr, args=(i, accion)) for i, accion in enumerate(acciones)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=30)
        return resultados

    def agendar(self, mascota, inicio):
        return lambda: AgendaService.agendar(mascota=mascota, veterinario=self.veterinario, servicio=self.servicio,
                                             inicio=inicio)

    def test_dos_clientes_reservan_el_mismo_turno_y_solo_uno_lo_consigue(self):
        resultados = self.a_la_vez(self.agendar(self.milo, self.hora(9, 30)), self.agendar(self.rocky, self.hora(9, 30)))

        citas = [r for r in resultados if isinstance(r, Cita)]
        avisos = [r for r in resultados if isinstance(r, ValidationError)]
        self.assertEqual((len(citas), len(avisos)), (1, 1))
        self.assertEqual(avisos[0].messages, [TURNO_OCUPADO])
        self.assertEqual(Cita.objects.filter(inicio=self.hora(9, 30)).exclude(estado=EstadoCita.CANCELADA).count(), 1)

    def test_reprogramar_y_agendar_al_mismo_turno_no_pierde_la_reserva(self):
        # Milo tiene las 9:00 y se mueve a las 10:00 justo cuando Rocky reserva las 10:00
        cita_milo = self.agendar(self.milo, self.hora(9))()
        resultados = self.a_la_vez(lambda: AgendaService.reprogramar(cita_milo, self.hora(10)),
                                   self.agendar(self.rocky, self.hora(10)))

        self.assertEqual(sum(isinstance(r, ValidationError) for r in resultados), 1)
        self.assertEqual(Cita.objects.filter(inicio=self.hora(10)).count(), 1)
        cita_milo.refresh_from_db()
        # Si Milo perdió, conserva su hora de antes: la reprogramación es una sola operación
        self.assertIn(cita_milo.inicio, (self.hora(9), self.hora(10)))
        self.assertEqual(cita_milo.estado, EstadoCita.CONFIRMADA)
