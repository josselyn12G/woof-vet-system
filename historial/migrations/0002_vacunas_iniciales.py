"""
Carga el catálogo inicial de vacunas (las más comunes en la clínica), cada una con su especie y su refuerzo.
La lista va escrita aquí (y no importada del código) para que la migración dé siempre el mismo resultado.
Si una especie no existe en la base, sus vacunas se saltan.
"""
from django.db import migrations

ANUAL = 365

# (código de la especie, nombre, refuerzo cada días)
VACUNAS = [
    ('perro', 'Rabia', ANUAL),
    ('perro', 'Polivalente canina (séxtuple)', ANUAL),
    ('perro', 'Tos de las perreras (Bordetella)', ANUAL),
    ('perro', 'Leptospirosis', ANUAL),
    ('gato', 'Rabia', ANUAL),
    ('gato', 'Triple felina', ANUAL),
    ('gato', 'Leucemia felina', ANUAL),
    ('conejo', 'Mixomatosis y hemorrágica vírica', ANUAL),
    ('huron', 'Moquillo (hurón)', ANUAL),
]


def cargar_vacunas(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Vacuna = apps.get_model('historial', 'Vacuna')
    especies = {especie.codigo: especie for especie in Especie.objects.all()}
    for codigo, nombre, refuerzo in VACUNAS:
        if codigo in especies:
            Vacuna.objects.get_or_create(nombre=nombre, especie=especies[codigo],
                                         defaults={'refuerzo_cada_dias': refuerzo})


def quitar_vacunas(apps, schema_editor):
    """Para deshacer: borra solo las vacunas de la lista que nunca se aplicaron."""
    Vacuna = apps.get_model('historial', 'Vacuna')
    for codigo, nombre, _ in VACUNAS:
        Vacuna.objects.filter(nombre=nombre, especie__codigo=codigo, aplicaciones__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('historial', '0001_inicial'),
        ('mascotas', '0006_mascota_especie_raza_fk'),
    ]

    operations = [
        migrations.RunPython(cargar_vacunas, quitar_vacunas),
    ]
