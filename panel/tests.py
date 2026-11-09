from django.test import TestCase
from django.urls import reverse

from cuentas.models import Roles
from cuentas.tests import usuario_con_rol

from .services import variacion


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
