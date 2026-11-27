"""País → provincia → ciudad: las listas de los desplegables y la regla de que encajen entre sí."""
from django.core.exceptions import ValidationError

from compartido.cache import memorizar
from cuentas.models import Ciudad, Pais, Provincia

PAIS_POR_DEFECTO = 'Ecuador'

# El árbol país → provincias → ciudades casi nunca cambia: se guarda entero en el caché (cuentas/signals.py lo
# borra cuando alguien edita una provincia o una ciudad)
CLAVE_ARBOL = 'ubicacion:arbol'


def armar_arbol():
    """Dos consultas: {'provincias': {pais_id: [opción, ...]}, 'ciudades': {provincia_id: [opción, ...]}}."""
    arbol = {'provincias': {}, 'ciudades': {}}
    for fila in Provincia.objects.order_by('nombre').values('id', 'nombre', 'pais_id'):
        arbol['provincias'].setdefault(fila['pais_id'], []).append({'id': fila['id'], 'nombre': fila['nombre']})
    for fila in Ciudad.objects.order_by('nombre').values('id', 'nombre', 'provincia_id'):
        arbol['ciudades'].setdefault(fila['provincia_id'], []).append({'id': fila['id'], 'nombre': fila['nombre']})
    return arbol


class UbicacionService:

    @staticmethod
    def paises():
        return Pais.objects.all()

    @staticmethod
    def pais_por_defecto():
        """Ecuador, el país que el registro deja elegido al abrirse (None si todavía no se cargó)."""
        return Pais.objects.filter(nombre=PAIS_POR_DEFECTO).first()

    @staticmethod
    def provincias_de(pais_id):
        """Las provincias del país (ninguna si no se eligió país)."""
        return Provincia.objects.filter(pais_id=pais_id) if pais_id else Provincia.objects.none()

    @staticmethod
    def ciudades_de(provincia_id):
        """Las ciudades de la provincia (ninguna si no se eligió provincia)."""
        return Ciudad.objects.filter(provincia_id=provincia_id) if provincia_id else Ciudad.objects.none()

    @staticmethod
    def opciones_de_provincias(pais_id):
        """Las provincias del país como [{'id', 'nombre'}] para ubicacion.js, desde el caché."""
        return memorizar(CLAVE_ARBOL, armar_arbol)['provincias'].get(pais_id, [])

    @staticmethod
    def opciones_de_ciudades(provincia_id):
        """Las ciudades de la provincia como [{'id', 'nombre'}] para ubicacion.js, desde el caché."""
        return memorizar(CLAVE_ARBOL, armar_arbol)['ciudades'].get(provincia_id, [])

    @staticmethod
    def validar(pais, provincia, ciudad):
        """
        La regla de los desplegables dependientes, en el servidor (decisión d8): la ciudad pertenece a la provincia
        y la provincia al país. Así no sirve armar a mano un POST con una ciudad de otra provincia.
        """
        if provincia.pais_id != pais.pk:
            raise ValidationError({'provincia': f'{provincia} no es una provincia de {pais}.'})
        if ciudad.provincia_id != provincia.pk:
            raise ValidationError({'ciudad': f'{ciudad} no es una ciudad de {provincia}.'})
