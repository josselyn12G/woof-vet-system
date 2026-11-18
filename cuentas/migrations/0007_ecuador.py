"""
Carga Ecuador con sus 24 provincias y las ciudades principales de cada una (la capital primero).
La lista va escrita aquí (y no importada del código) para que la migración dé siempre el mismo resultado.
Se pueden agregar más países, provincias o ciudades desde /admin/.
"""
from django.db import migrations

ECUADOR = {
    'Azuay': ['Cuenca', 'Gualaceo', 'Paute', 'Sígsig'],
    'Bolívar': ['Guaranda', 'Chillanes', 'San Miguel'],
    'Cañar': ['Azogues', 'Cañar', 'La Troncal'],
    'Carchi': ['Tulcán', 'El Ángel', 'San Gabriel'],
    'Chimborazo': ['Riobamba', 'Alausí', 'Guano'],
    'Cotopaxi': ['Latacunga', 'La Maná', 'Pujilí', 'Salcedo'],
    'El Oro': ['Machala', 'Huaquillas', 'Pasaje', 'Santa Rosa'],
    'Esmeraldas': ['Esmeraldas', 'Atacames', 'Quinindé'],
    'Galápagos': ['Puerto Baquerizo Moreno', 'Puerto Ayora', 'Puerto Villamil'],
    'Guayas': ['Guayaquil', 'Daule', 'Durán', 'Milagro', 'Samborondón'],
    'Imbabura': ['Ibarra', 'Atuntaqui', 'Cotacachi', 'Otavalo'],
    'Loja': ['Loja', 'Cariamanga', 'Catamayo'],
    'Los Ríos': ['Babahoyo', 'Quevedo', 'Ventanas', 'Vinces'],
    'Manabí': ['Portoviejo', 'Bahía de Caráquez', 'Chone', 'Jipijapa', 'Manta'],
    'Morona Santiago': ['Macas', 'Gualaquiza', 'Sucúa'],
    'Napo': ['Tena', 'Archidona', 'El Chaco'],
    'Orellana': ['Francisco de Orellana (El Coca)', 'La Joya de los Sachas'],
    'Pastaza': ['Puyo', 'Mera'],
    'Pichincha': ['Quito', 'Cayambe', 'Machachi', 'Sangolquí', 'Tabacundo'],
    'Santa Elena': ['Santa Elena', 'La Libertad', 'Salinas'],
    'Santo Domingo de los Tsáchilas': ['Santo Domingo', 'La Concordia'],
    'Sucumbíos': ['Nueva Loja', 'Shushufindi'],
    'Tungurahua': ['Ambato', 'Baños de Agua Santa', 'Pelileo', 'Píllaro'],
    'Zamora Chinchipe': ['Zamora', 'Yantzaza', 'Zumbi'],
}


def cargar_ecuador(apps, schema_editor):
    Pais = apps.get_model('cuentas', 'Pais')
    Provincia = apps.get_model('cuentas', 'Provincia')
    Ciudad = apps.get_model('cuentas', 'Ciudad')
    ecuador, _ = Pais.objects.get_or_create(nombre='Ecuador')
    for nombre_provincia, ciudades in ECUADOR.items():
        provincia, _ = Provincia.objects.get_or_create(pais=ecuador, nombre=nombre_provincia)
        for nombre_ciudad in ciudades:
            Ciudad.objects.get_or_create(provincia=provincia, nombre=nombre_ciudad)


def quitar_ecuador(apps, schema_editor):
    """Para deshacer: borra Ecuador (y en cascada sus provincias y ciudades) si ningún usuario lo usa."""
    Pais = apps.get_model('cuentas', 'Pais')
    Usuario = apps.get_model('cuentas', 'Usuario')
    if not Usuario.objects.filter(ciudad__provincia__pais__nombre='Ecuador').exists():
        Pais.objects.filter(nombre='Ecuador').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0006_ubicacion'),
    ]

    operations = [
        migrations.RunPython(cargar_ecuador, quitar_ecuador),
    ]
