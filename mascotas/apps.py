from django.apps import AppConfig


class MascotasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mascotas'

    def ready(self):
        from . import signals  # noqa: F401 (conecta los observadores que limpian el caché)
