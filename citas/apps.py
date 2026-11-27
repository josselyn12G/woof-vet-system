from django.apps import AppConfig


class CitasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'citas'

    def ready(self):
        from . import signals  # noqa: F401 (conecta los observadores que limpian el caché)
