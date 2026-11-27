from unittest.mock import Mock

from django.core.cache import cache
from django.test import TestCase

from .cache import memorizar, olvidar
from .pruebas import con_cache


@con_cache
class CacheAsideTests(TestCase):
    """memorizar(): el primer pedido calcula (fallo) y los siguientes salen de la memoria (acierto)."""

    def test_el_fallo_calcula_y_el_acierto_no(self):
        calcular = Mock(return_value=['Consulta general'])
        self.assertEqual(memorizar('prueba', calcular), ['Consulta general'])   # fallo: calcula
        self.assertEqual(memorizar('prueba', calcular), ['Consulta general'])   # acierto: no vuelve a calcular
        self.assertEqual(calcular.call_count, 1)

    def test_olvidar_borra_la_clave_cuando_la_transaccion_termina_bien(self):
        memorizar('prueba', lambda: ['vieja'])
        with self.captureOnCommitCallbacks(execute=True):
            olvidar('prueba')
            self.assertEqual(cache.get('prueba'), ['vieja'])   # dentro de la transacción todavía no se borra
        self.assertIsNone(cache.get('prueba'))
        self.assertEqual(memorizar('prueba', lambda: ['nueva']), ['nueva'])


class SinCacheEnLasPruebasTests(TestCase):
    def test_fuera_de_con_cache_siempre_calcula(self):
        calcular = Mock(return_value=[])
        memorizar('prueba', calcular)
        memorizar('prueba', calcular)
        self.assertEqual(calcular.call_count, 2)   # DummyCache: una prueba no ve lo que guardó otra
