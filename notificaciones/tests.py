"""
Pruebas de los avisos: se guardan para la campana, salen por correo, se reintentan si fallan y llegan como
recordatorios de citas y vacunas. Los avisos de citas llegan por los eventos de citas (citas/eventos.py).
"""
import re
from datetime import time, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from citas.eventos import anunciar_al_confirmar, cita_agendada
from citas.models import Cita, EstadoCita
from citas.tests import crear_horario, crear_servicio, crear_veterinario
from cuentas.models import Roles
from historial.models import Vacuna, VacunaAplicada
from mascotas.tests import crear_mascota, crear_usuario

from .models import Notificacion, TipoNotificacion
from .services import MAX_INTENTOS_CORREO, NotificacionService


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
        with patch('notificaciones.services.threading.Thread') as hilo:
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
                self.assertLogs('notificaciones.services', level='ERROR'):
            cita = self.agendar()
        self.assertEqual(cita.estado, EstadoCita.CONFIRMADA)
        self.assertEqual(Notificacion.objects.count(), 2)

    @override_settings(CORREO_AVISOS=False)
    def test_con_los_correos_apagados_solo_se_guardan_los_avisos(self):
        self.agendar()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notificacion.objects.count(), 2)


class ReintentoDeCorreosTests(TestCase):
    """
    El fallback de los avisos: si el correo no sale, el aviso queda en la campana y enviar_recordatorios
    lo reintenta más tarde, pocas veces (MAX_INTENTOS_CORREO) y nunca al instante.
    """

    def setUp(self):
        self.veterinario = crear_veterinario()
        self.servicio = crear_servicio()
        self.cliente = crear_usuario('ana', email='ana@correo.ec')
        self.mascota = crear_mascota(self.cliente)
        inicio = timezone.now() + timedelta(days=3)
        self.cita = Cita.objects.create(mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
                                        inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'))

    def aviso(self, hace=timedelta(hours=1), cita=None, **campos):
        """Un aviso cuyo correo no salió, creado hace un rato (creado es auto_now_add: se corrige con update)."""
        aviso = Notificacion.objects.create(usuario=self.cliente, cita=cita or self.cita,
                                            tipo=TipoNotificacion.AGENDADA, mensaje='Tu cita quedó confirmada.',
                                            **campos)
        Notificacion.objects.filter(pk=aviso.pk).update(creado=timezone.now() - hace)
        return Notificacion.objects.get(pk=aviso.pk)

    def smtp_caido(self):
        return patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('SMTP caído'))

    def test_el_envio_registra_si_salio_y_cuantas_veces_se_intento(self):
        aviso = self.aviso()
        self.assertTrue(NotificacionService.enviar(aviso))
        aviso.refresh_from_db()
        self.assertTrue(aviso.correo_enviado)
        self.assertEqual(aviso.intentos_correo, 1)

    def test_si_el_correo_falla_cuenta_el_intento_y_queda_pendiente(self):
        aviso = self.aviso()
        with self.smtp_caido(), self.assertLogs('notificaciones.services', level='ERROR'):
            self.assertFalse(NotificacionService.enviar(aviso))
        aviso.refresh_from_db()
        self.assertFalse(aviso.correo_enviado)
        self.assertEqual(aviso.intentos_correo, 1)

    def test_un_aviso_que_ya_salio_no_se_vuelve_a_enviar(self):
        aviso = self.aviso()
        NotificacionService.enviar(aviso)
        self.assertFalse(NotificacionService.enviar(aviso))
        self.assertEqual(len(mail.outbox), 1)

    def test_si_otro_proceso_ya_conto_el_intento_no_se_envia_dos_veces(self):
        aviso = self.aviso()
        # Otro proceso (el hilo del primer envío o el comando) lo reservó después de que se leyó este aviso
        Notificacion.objects.filter(pk=aviso.pk).update(intentos_correo=1)
        self.assertFalse(NotificacionService.enviar(aviso))
        self.assertEqual(len(mail.outbox), 0)

    def test_el_comando_reintenta_los_correos_que_fallaron(self):
        aviso = self.aviso(intentos_correo=1)
        salida = StringIO()
        call_command('enviar_recordatorios', stdout=salida)
        self.assertIn('Se reenviaron 1 correo que habían fallado.', salida.getvalue())
        self.assertEqual([correo.to for correo in mail.outbox], [['ana@correo.ec']])
        aviso.refresh_from_db()
        self.assertTrue(aviso.correo_enviado)
        self.assertEqual(aviso.intentos_correo, 2)

    def test_no_reintenta_enseguida_ni_avisos_viejos(self):
        self.aviso(hace=timedelta(minutes=5), intentos_correo=1)   # recién falló: se espera media hora
        self.aviso(hace=timedelta(days=3), intentos_correo=1)      # ya no tiene sentido mandarlo
        self.assertEqual(NotificacionService.reintentar_correos(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_se_rinde_despues_del_maximo_de_intentos(self):
        self.aviso(intentos_correo=MAX_INTENTOS_CORREO)
        self.assertEqual(NotificacionService.reintentar_correos(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_reintenta_el_aviso_de_una_cita_que_ya_empezo(self):
        inicio = timezone.now() - timedelta(hours=2)
        pasada = Cita.objects.create(mascota=self.mascota, veterinario=self.veterinario, servicio=self.servicio,
                                     inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'))
        self.aviso(cita=pasada, intentos_correo=1)
        self.assertEqual(NotificacionService.reintentar_correos(), 0)

    def test_tres_fallas_seguidas_dejan_el_aviso_solo_en_la_campana(self):
        aviso = self.aviso()
        with self.smtp_caido(), self.assertLogs('notificaciones.services', level='ERROR'):
            for _ in range(MAX_INTENTOS_CORREO + 1):
                NotificacionService.reintentar_correos()
        aviso.refresh_from_db()
        self.assertEqual(aviso.intentos_correo, MAX_INTENTOS_CORREO)
        self.assertFalse(aviso.correo_enviado)
        self.assertEqual(NotificacionService.no_leidas(self.cliente), 1)   # el plan B sigue ahí

    @override_settings(CORREO_AVISOS=False)
    def test_con_el_correo_apagado_no_reintenta_nada(self):
        aviso = self.aviso()
        self.assertEqual(NotificacionService.reintentar_correos(), 0)
        aviso.refresh_from_db()
        self.assertEqual(aviso.intentos_correo, 0)


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


class RecordatoriosDeVacunasTests(TestCase):
    """enviar_recordatorios también avisa al dueño una semana antes de la próxima dosis de una vacuna (HU-37)."""

    def setUp(self):
        self.hoy = timezone.localdate()
        self.veterinario = crear_veterinario(email='sofia@woof.ec')
        self.cliente = crear_usuario('ana', email='ana@correo.ec')
        self.milo = crear_mascota(self.cliente, nombre='Milo')
        self.rabia = Vacuna.objects.get(nombre='Rabia', especie__codigo='perro')

    def dosis(self, proxima_en_dias, aplicada_hace_dias=300):
        return VacunaAplicada.objects.create(
            mascota=self.milo, vacuna=self.rabia, veterinario=self.veterinario,
            fecha_aplicacion=self.hoy - timedelta(days=aplicada_hace_dias),
            proxima_dosis=self.hoy + timedelta(days=proxima_en_dias),
        )

    def ejecutar(self):
        salida = StringIO()
        call_command('enviar_recordatorios', stdout=salida)
        return salida.getvalue()

    def test_avisa_al_dueno_una_semana_antes(self):
        aplicada = self.dosis(7)
        self.assertIn('Se enviaron 1 recordatorio de vacuna.', self.ejecutar())
        self.assertEqual([correo.to for correo in mail.outbox], [['ana@correo.ec']])
        self.assertEqual(mail.outbox[0].subject, 'Woof · Recordatorio de vacuna')
        aviso = Notificacion.objects.get(vacuna_aplicada=aplicada, tipo=TipoNotificacion.VACUNA)
        self.assertEqual(aviso.usuario, self.cliente)
        self.assertIn('Milo', aviso.mensaje)
        self.assertIn('Rabia', aviso.mensaje)
        self.assertIn('en 7 días', aviso.mensaje)
        self.assertIn('carnet de vacunación', mail.outbox[0].body)

    def test_si_faltan_menos_de_7_dias_tambien_avisa(self):
        self.dosis(1)
        self.ejecutar()
        self.assertIn('mañana', Notificacion.objects.get(tipo=TipoNotificacion.VACUNA).mensaje)

    def test_no_avisa_dos_veces_la_misma_dosis(self):
        self.dosis(5)
        self.ejecutar()
        self.assertIn('Se enviaron 0 recordatorios de vacunas.', self.ejecutar())
        self.assertEqual(Notificacion.objects.filter(tipo=TipoNotificacion.VACUNA).count(), 1)

    def test_fuera_de_la_semana_o_ya_vencida_no_avisa(self):
        self.dosis(8)
        self.dosis(-1, aplicada_hace_dias=400)
        self.ejecutar()
        self.assertFalse(Notificacion.objects.filter(tipo=TipoNotificacion.VACUNA).exists())

    def test_si_ya_recibio_otra_dosis_no_avisa(self):
        self.dosis(3)
        self.dosis(360, aplicada_hace_dias=5)   # ya se vacunó otra vez
        self.ejecutar()
        self.assertFalse(Notificacion.objects.filter(tipo=TipoNotificacion.VACUNA).exists())

    def test_la_base_no_acepta_dos_recordatorios_de_la_misma_dosis(self):
        aplicada = self.dosis(4)
        NotificacionService.recordatorio_vacuna(aplicada)
        self.assertIsNone(NotificacionService.recordatorio_vacuna(aplicada))
        with self.assertRaises(IntegrityError):
            Notificacion.objects.create(usuario=self.cliente, vacuna_aplicada=aplicada,
                                        tipo=TipoNotificacion.VACUNA, mensaje='otra vez')

    def test_la_campana_muestra_el_recordatorio_de_vacuna(self):
        self.dosis(6)
        self.ejecutar()
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('notificaciones:lista'))
        self.assertContains(respuesta, 'Recordatorio de vacuna')
        self.assertContains(respuesta, 'bi-shield-plus')


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
        respuesta = self.client.get(reverse('notificaciones:lista'))
        self.assertContains(respuesta, 'Primero')
        self.assertNotContains(respuesta, 'Ajeno')     # solo los suyos
        self.assertContains(respuesta, 'Nuevo', count=2)
        self.assertEqual(NotificacionService.no_leidas(self.cliente), 0)
        self.assertNotContains(self.client.get(reverse('notificaciones:lista')), 'Nuevo')

    def test_pide_iniciar_sesion(self):
        self.client.logout()
        self.assertIn(reverse('cuentas:login'), self.client.get(reverse('notificaciones:lista')).url)


class PanelDeLaCampanaTests(TestCase):
    """El panel que abre la campana: avisos en Hoy / Esta semana / Antes y, al verlos, quedan leídos."""

    def setUp(self):
        self.ana = crear_usuario('ana', first_name='Ana')
        self.client.force_login(self.ana)
        ahora = timezone.now()
        for dias, tipo in ((0, TipoNotificacion.AGENDADA), (3, TipoNotificacion.REPROGRAMADA), (20, TipoNotificacion.CANCELADA)):
            aviso = Notificacion.objects.create(usuario=self.ana, tipo=tipo, mensaje=f'Aviso de hace {dias} días')
            Notificacion.objects.filter(pk=aviso.pk).update(creado=ahora - timedelta(days=dias, minutes=5))

    def test_agrupa_en_hoy_esta_semana_y_antes(self):
        respuesta = self.client.get(reverse('notificaciones:panel'))
        grupos = {clave: [a.mensaje for a in avisos] for clave, _, avisos in respuesta.context['grupos']}
        self.assertEqual(grupos, {'hoy': ['Aviso de hace 0 días'], 'semana': ['Aviso de hace 3 días'],
                                  'antes': ['Aviso de hace 20 días']})
        self.assertEqual(respuesta.context['grupo_inicial'], 'hoy')
        self.assertContains(respuesta, 'Ver todas')
        self.assertContains(respuesta, 'Hace 5 min')

    def test_al_abrirlo_quedan_leidas(self):
        self.assertEqual(Notificacion.objects.filter(usuario=self.ana, leida=False).count(), 3)
        self.client.get(reverse('notificaciones:panel'))
        self.assertFalse(Notificacion.objects.filter(usuario=self.ana, leida=False).exists())

    def test_solo_ve_las_suyas_y_pide_sesion(self):
        otro = crear_usuario('luis')
        Notificacion.objects.create(usuario=otro, tipo=TipoNotificacion.AGENDADA, mensaje='De Luis')
        self.assertNotContains(self.client.get(reverse('notificaciones:panel')), 'De Luis')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('notificaciones:panel')).status_code, 302)


class EventosDeCitasTests(TestCase):
    """citas anuncia el evento y no sabe quién escucha; notificaciones lo recibe (patrón Observer)."""

    def setUp(self):
        veterinario = crear_veterinario()
        inicio = timezone.now() + timedelta(days=2)
        self.cita = Cita.objects.create(
            mascota=crear_mascota(crear_usuario('ana')), veterinario=veterinario, servicio=crear_servicio(),
            inicio=inicio, fin=inicio + timedelta(minutes=30), precio=Decimal('25.00'),
        )

    def test_el_evento_de_cita_agendada_crea_los_dos_avisos(self):
        with self.captureOnCommitCallbacks(execute=True):
            anunciar_al_confirmar(cita_agendada, self.cita)
        self.assertEqual(Notificacion.objects.filter(cita=self.cita, tipo=TipoNotificacion.AGENDADA).count(), 2)

    def test_si_la_transaccion_no_se_confirma_nadie_recibe_el_evento(self):
        with self.captureOnCommitCallbacks(execute=False):
            anunciar_al_confirmar(cita_agendada, self.cita)
        self.assertFalse(Notificacion.objects.exists())


class DependenciasEntreAppsTests(SimpleTestCase):
    """
    La regla que motivó separar esta app: citas no importa notificaciones ni historial (así no hay ciclos).
    notificaciones sí puede depender de citas e historial.
    """
    IMPORTA = re.compile(r'^\s*(from|import)\s+(notificaciones|historial)\b', re.MULTILINE)

    def test_citas_no_depende_de_notificaciones_ni_de_historial(self):
        for archivo in Path(settings.BASE_DIR, 'citas').rglob('*.py'):
            if 'migrations' in archivo.parts or archivo.name == 'tests.py':
                continue
            with self.subTest(archivo=archivo.name):
                self.assertIsNone(self.IMPORTA.search(archivo.read_text(encoding='utf-8')))
