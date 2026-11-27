from django.db import migrations


class Migration(migrations.Migration):
    """
    Notificacion se mudó a la app notificaciones. Aquí solo se borra del estado de Django (lo que Django cree que
    tiene citas): la tabla y sus filas no se tocan. notificaciones/0001 la vuelve a declarar como suya.
    """

    dependencies = [
        ('citas', '0006_notificacion_correo_enviado'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name='Notificacion')],
            database_operations=[],
        ),
    ]
