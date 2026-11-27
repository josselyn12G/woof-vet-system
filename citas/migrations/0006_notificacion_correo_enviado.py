from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Registra si el correo de cada aviso salió y cuántas veces se intentó (para reintentar los que fallaron).

    Los avisos que ya existían quedan como enviados (default=True al agregar la columna): no sabemos si su
    correo salió y no queremos mandar correos viejos. Después el default pasa a False para los nuevos.
    """

    dependencies = [
        ('citas', '0005_recordatorio_vacuna'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificacion',
            name='correo_enviado',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='notificacion',
            name='correo_enviado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notificacion',
            name='intentos_correo',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
