"""
Paso 1 de 3 para pasar Mascota.especie y Mascota.raza de texto a la tabla de especies y razas:
agrega las columnas nuevas, vacías por ahora. Van en migraciones separadas porque PostgreSQL (Neon)
no deja cambiar los datos y la estructura de la misma tabla en una sola transacción.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0003_especie_raza'),
    ]

    operations = [
        migrations.AddField(
            model_name='mascota',
            name='especie_nueva',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                                    to='mascotas.especie'),
        ),
        migrations.AddField(
            model_name='mascota',
            name='raza_nueva',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                                    to='mascotas.raza'),
        ),
    ]
