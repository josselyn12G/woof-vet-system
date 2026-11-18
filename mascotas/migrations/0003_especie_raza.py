"""
Especies y razas en la base (antes la especie era una lista fija en el código y la raza, texto libre).

Crea las tablas y carga la lista inicial: muchas razas de perro y de gato (las más comunes) y algunas
de otras especies. "perro", "gato" y "otro" conservan el código que ya tenían las mascotas.
La lista va escrita aquí (y no importada del código) para que la migración dé siempre el mismo resultado.
"""
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

# (código, nombre, plural, orden, razas)
CATALOGO = [
    ('perro', 'Perro', 'Perros', 1, [
        'Mestizo', 'Akita Inu', 'American Bully', 'Basset Hound', 'Beagle', 'Bichón Frisé', 'Bichón Maltés',
        'Border Collie', 'Bóxer', 'Bull Terrier', 'Bulldog Francés', 'Bulldog Inglés', 'Cane Corso',
        'Cavalier King Charles', 'Chihuahua', 'Chow Chow', 'Cocker Spaniel', 'Collie', 'Corgi', 'Dálmata',
        'Dóberman', 'Dogo Argentino', 'Fox Terrier', 'Galgo', 'Golden Retriever', 'Gran Danés',
        'Husky Siberiano', 'Jack Russell Terrier', 'Labrador Retriever', 'Lhasa Apso', 'Mastín Napolitano',
        'Pastor Alemán', 'Pastor Belga Malinois', 'Pekinés', 'Pinscher Miniatura', 'Pitbull', 'Pomerania',
        'Poodle', 'Pug', 'Rottweiler', 'Samoyedo', 'San Bernardo', 'Schnauzer', 'Shar Pei', 'Shiba Inu',
        'Shih Tzu', 'Sin Pelo del Perú', 'Weimaraner', 'West Highland White Terrier', 'Yorkshire Terrier',
    ]),
    ('gato', 'Gato', 'Gatos', 2, [
        'Mestizo', 'Abisinio', 'Angora Turco', 'Azul Ruso', 'Bengalí', 'Bombay', 'Bosque de Noruega',
        'British Shorthair', 'Burmés', 'Devon Rex', 'Esfinge', 'Exótico de Pelo Corto', 'Himalayo',
        'Maine Coon', 'Manx', 'Persa', 'Ragdoll', 'Scottish Fold', 'Siamés', 'Siberiano', 'Van Turco',
    ]),
    ('conejo', 'Conejo', 'Conejos', 3, [
        'Mestizo', 'Angora', 'Belier', 'Cabeza de León', 'Californiano', 'Enano Holandés', 'Gigante de Flandes',
        'Hotot', 'Rex',
    ]),
    ('hamster', 'Hámster', 'Hámsters', 4, ['Campbell', 'Chino', 'Roborovski', 'Ruso', 'Sirio']),
    ('cobayo', 'Cobayo', 'Cobayos', 5, ['Mestizo', 'Abisinio', 'Americano', 'Peruano', 'Rex', 'Skinny', 'Teddy']),
    ('huron', 'Hurón', 'Hurones', 6, ['Mestizo', 'Angora', 'Estándar']),
    ('ave', 'Ave', 'Aves', 7, [
        'Agapornis', 'Cacatúa', 'Canario', 'Diamante Mandarín', 'Gallina', 'Guacamayo', 'Loro', 'Ninfa', 'Paloma',
        'Periquito',
    ]),
    ('tortuga', 'Tortuga', 'Tortugas', 8, ['Morrocoy', 'Tortuga de Orejas Rojas', 'Tortuga de Tierra', 'Tortuga Mapa']),
    ('pez', 'Pez', 'Peces', 9, ['Betta', 'Disco', 'Goldfish', 'Guppy', 'Koi', 'Molly', 'Pez Ángel', 'Tetra Neón']),
    ('otro', 'Otro', 'Otras especies', 99, ['Mestizo']),
]


def cargar_catalogo(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Raza = apps.get_model('mascotas', 'Raza')
    for codigo, nombre, plural, orden, razas in CATALOGO:
        especie, _ = Especie.objects.get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'plural': plural, 'orden': orden},
        )
        for raza in razas:
            Raza.objects.get_or_create(especie=especie, nombre=raza)


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0002_mascota_foto'),
    ]

    operations = [
        migrations.CreateModel(
            name='Especie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=40, unique=True)),
                ('plural', models.CharField(max_length=40)),
                ('codigo', models.SlugField(max_length=30, unique=True)),
                ('orden', models.PositiveSmallIntegerField(default=50, help_text='Las de número menor salen primero.')),
                ('activa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'especie',
                'verbose_name_plural': 'especies',
                'ordering': ['orden', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='Raza',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=60)),
                ('activa', models.BooleanField(default=True)),
                ('especie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='razas',
                                              to='mascotas.especie')),
            ],
            options={
                'verbose_name': 'raza',
                'verbose_name_plural': 'razas',
                'ordering': ['especie__orden', 'nombre'],
                'constraints': [
                    models.UniqueConstraint(django.db.models.functions.text.Lower('nombre'), models.F('especie'),
                                            name='raza_unica_por_especie'),
                ],
            },
        ),
        migrations.RunPython(cargar_catalogo, migrations.RunPython.noop),
    ]
