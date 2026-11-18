"""
Paso 3 de 3: borra las columnas de texto (y la regla que solo aceptaba perro, gato u otro) y deja
las nuevas con el nombre de siempre: especie (obligatoria) y raza (opcional).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0005_mascotas_a_mestizo'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='mascota',
            name='mascota_especie_valida',
        ),
        # Valores por defecto en las columnas viejas: solo sirven para poder deshacer la migración
        # (al volver a crearlas, las filas que ya existen necesitan un valor; luego 0005 pone el real)
        migrations.AlterField(
            model_name='mascota',
            name='especie',
            field=models.CharField(choices=[('perro', 'Perro'), ('gato', 'Gato'), ('otro', 'Otro')], default='otro',
                                   max_length=10),
        ),
        migrations.AlterField(
            model_name='mascota',
            name='raza',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.RemoveField(
            model_name='mascota',
            name='especie',
        ),
        migrations.RemoveField(
            model_name='mascota',
            name='raza',
        ),
        migrations.RenameField(
            model_name='mascota',
            old_name='especie_nueva',
            new_name='especie',
        ),
        migrations.RenameField(
            model_name='mascota',
            old_name='raza_nueva',
            new_name='raza',
        ),
        migrations.AlterField(
            model_name='mascota',
            name='especie',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mascotas',
                                    to='mascotas.especie'),
        ),
        migrations.AlterField(
            model_name='mascota',
            name='raza',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='mascotas', to='mascotas.raza'),
        ),
    ]
