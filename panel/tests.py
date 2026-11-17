from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from citas.models import Calificacion, Servicio
from citas.services import AgendaService
from cuentas.models import PerfilVeterinario, Roles
from cuentas.tests import usuario_con_rol
from historial.models import Consulta, Prescripcion, VacunaAplicada

from .services import variacion
from .services.demo import CLAVE_DEMO, proximo_dia_habil


class PanelTests(TestCase):
    """/panel/ no dibuja nada: manda a cada usuario a la portada de su rol."""

    def test_redirige_a_la_portada_de_cada_rol(self):
        destinos = [
            (Roles.CLIENTE, 'panel:inicio_cliente'),
            (Roles.VETERINARIO, 'panel:inicio_veterinario'),
            (Roles.ADMINISTRADOR, 'panel:inicio_administrador'),
        ]
        for numero, (rol, destino) in enumerate(destinos, start=1):
            with self.subTest(rol=rol):
                self.client.force_login(usuario_con_rol(f'persona{numero}', rol, numero))
                respuesta = self.client.get(reverse('panel:panel'))
                self.assertRedirects(respuesta, reverse(destino))

    def test_periodo_inventado_vuelve_al_de_siempre(self):
        # ?periodo= viene de la URL: un valor que no existe no rompe la página, usa el período por defecto
        self.client.force_login(usuario_con_rol('jefa', Roles.ADMINISTRADOR, 1))
        respuesta = self.client.get(reverse('panel:inicio_administrador'), {'periodo': 'nada'})
        self.assertEqual(respuesta.context['periodo'], 'mes')

        self.client.force_login(usuario_con_rol('dra.paredes', Roles.VETERINARIO, 2))
        respuesta = self.client.get(reverse('panel:inicio_veterinario'), {'periodo': 'nada'})
        self.assertEqual(respuesta.context['periodo'], '7d')

    def test_variacion_no_inventa_porcentajes(self):
        # Sin datos del período anterior no hay porcentaje que calcular
        self.assertEqual(variacion(0, 0), {'texto': '—', 'tipo': 'neutro'})
        self.assertEqual(variacion(3, 0), {'texto': '+3 nuevas', 'tipo': 'nuevo'})
        self.assertEqual(variacion(15, 10), {'texto': '50,0%', 'tipo': 'sube'})
        self.assertEqual(variacion(5, 10), {'texto': '50,0%', 'tipo': 'baja'})


class CargarDemoTests(TestCase):
    """python manage.py cargar_demo: los datos del ejemplo del Documento de Análisis, relativos a hoy."""

    def cargar(self, confirmar=True):
        # La base de pruebas se borra al terminar: se confirma para que también corra sobre PostgreSQL (CI)
        salida = StringIO()
        call_command('cargar_demo', stdout=salida, confirmar=confirmar)
        return salida.getvalue()

    def test_carga_la_agenda_de_la_figura_1(self):
        self.assertIn('Demo cargada', self.cargar())
        paredes = get_user_model().objects.get(username='paredes')
        dia = proximo_dia_habil(timezone.localdate())
        espacios = AgendaService.espacios_disponibles(paredes, Servicio.objects.get(nombre='Consulta general'), dia)
        manana = [timezone.localtime(inicio).strftime('%H:%M') for inicio in espacios if inicio.hour < 13]
        self.assertEqual(manana, ['09:00', '10:30', '11:00', '11:30', '12:30'])

    def test_trae_historia_clinica_calificaciones_y_un_veterinario_sin_verificar(self):
        self.cargar()
        self.assertEqual(Consulta.objects.count(), 5)   # las 5 visitas atendidas de las dos semanas pasadas
        self.assertEqual(Prescripcion.objects.count(), 3)
        self.assertEqual(VacunaAplicada.objects.count(), 3)
        self.assertEqual(Calificacion.objects.count(), 4)
        self.assertFalse(PerfilVeterinario.objects.get(usuario__username='mora').verificado)

    def test_los_usuarios_entran_con_la_clave_de_la_demo(self):
        self.cargar()
        self.assertTrue(self.client.login(username='ana', password=CLAVE_DEMO))

    def test_correrlo_dos_veces_no_duplica_nada(self):
        self.cargar()
        usuarios = get_user_model().objects.count()
        self.assertIn('ya estaba cargada', self.cargar())
        self.assertEqual(get_user_model().objects.count(), usuarios)

    def test_en_una_base_que_no_es_sqlite_pide_confirmar(self):
        with patch.object(connection, 'vendor', 'postgresql'):
            with self.assertRaisesMessage(CommandError, '--confirmar'):
                self.cargar(confirmar=False)
        self.assertFalse(get_user_model().objects.filter(username='paredes').exists())
