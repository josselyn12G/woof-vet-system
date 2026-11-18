"""
Paso 2 de 3: cada mascota pasa a la especie de la tabla con el mismo código (perro, gato u otro)
y queda con la raza "Mestizo" de esa especie. La raza que se había escrito a mano no se conserva.
"""
from django.db import migrations

MESTIZO = 'Mestizo'


def pasar_a_la_tabla(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Raza = apps.get_model('mascotas', 'Raza')
    Mascota = apps.get_model('mascotas', 'Mascota')
    otro = Especie.objects.get(codigo='otro')
    for codigo in Mascota.objects.values_list('especie', flat=True).distinct():
        # Un valor que no sea perro, gato u otro (no debería haberlo: la base lo impedía) va a "Otro"
        especie = Especie.objects.filter(codigo=codigo).first() or otro
        mestizo, _ = Raza.objects.get_or_create(especie=especie, nombre=MESTIZO)
        Mascota.objects.filter(especie=codigo).update(especie_nueva=especie, raza_nueva=mestizo)


def volver_a_texto(apps, schema_editor):
    """Para deshacer la migración: el código de la especie y el nombre de la raza vuelven como texto."""
    Mascota = apps.get_model('mascotas', 'Mascota')
    for mascota in Mascota.objects.select_related('especie_nueva', 'raza_nueva'):
        codigo = mascota.especie_nueva.codigo if mascota.especie_nueva else 'otro'
        mascota.especie = codigo if codigo in ('perro', 'gato') else 'otro'
        mascota.raza = mascota.raza_nueva.nombre if mascota.raza_nueva else ''
        mascota.save(update_fields=['especie', 'raza'])


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0004_mascota_especie_raza_temporales'),
    ]

    operations = [
        migrations.RunPython(pasar_a_la_tabla, volver_a_texto),
    ]
