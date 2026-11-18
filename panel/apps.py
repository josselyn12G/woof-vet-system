from django.apps import AppConfig


class PanelConfig(AppConfig):
    """La portada de cada rol después del login. Junta cifras de cuentas, mascotas y citas, así que
    depende de las tres apps y ninguna depende de ella."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'panel'
