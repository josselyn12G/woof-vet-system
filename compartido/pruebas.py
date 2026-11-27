"""Ayudas para las pruebas del caché (en las pruebas el caché está apagado: ver CACHES en settings)."""
from django.core.cache import cache
from django.test import override_settings


def con_cache(clase):
    """Decorador de clases de prueba: prende un caché en memoria y lo vacía antes de cada prueba."""
    clase = override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'pruebas-woof',
    }})(clase)
    preparar = clase.setUp

    def setUp(self):
        cache.clear()
        preparar(self)

    clase.setUp = setUp
    return clase
