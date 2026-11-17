"""País → provincia → ciudad: las listas de los desplegables y la regla de que encajen entre sí."""
from django.core.exceptions import ValidationError

from cuentas.models import Ciudad, Pais, Provincia

PAIS_POR_DEFECTO = 'Ecuador'


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
    def validar(pais, provincia, ciudad):
        """
        La regla de los desplegables dependientes, en el servidor (decisión d8): la ciudad pertenece a la provincia
        y la provincia al país. Así no sirve armar a mano un POST con una ciudad de otra provincia.
        """
        if provincia.pais_id != pais.pk:
            raise ValidationError({'provincia': f'{provincia} no es una provincia de {pais}.'})
        if ciudad.provincia_id != provincia.pk:
            raise ValidationError({'ciudad': f'{ciudad} no es una ciudad de {provincia}.'})
