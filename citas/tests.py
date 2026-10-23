from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.test import TestCase
from django.urls import reverse

from cuentas.models import Roles
from mascotas.tests import crear_usuario

from .models import HorarioVeterinario, Servicio


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
