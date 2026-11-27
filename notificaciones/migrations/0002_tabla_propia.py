from django.db import migrations


class Migration(migrations.Migration):
    """La tabla pasa de citas_notificacion a notificaciones_notificacion (un RENAME: las filas se quedan)."""

    dependencies = [
        ('notificaciones', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(name='notificacion', table=None),
    ]
