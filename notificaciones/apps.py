from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notificaciones'

    def ready(self):
        from . import receptores  # noqa: F401 (se suscribe a los eventos de las citas)
