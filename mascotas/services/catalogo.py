from django.db.models import Count, Prefetch, ProtectedError, Q

from mascotas.models import Especie, Raza


class CatalogoService:
    """El catálogo de especies y razas que se ofrece al registrar una mascota (lo gestiona el superadministrador)."""

    @staticmethod
    def especies():
        return Especie.objects.all()

    @staticmethod
    def razas():
        return Raza.objects.all()

    @staticmethod
    def especies_para_elegir(actual_pk=None):
        """Las especies activas para el formulario de la mascota; al editar, también la que ya tiene."""
        return Especie.objects.filter(Q(activa=True) | Q(pk=actual_pk))

    @staticmethod
    def razas_para_elegir(especies, actual_pk=None):
        """Las razas activas de esas especies (al editar, también la que ya tiene), por especie y con Mestizo primero."""
        return (
            Raza.objects.filter(Q(activa=True, especie__in=especies) | Q(pk=actual_pk))
            .select_related('especie').mestizo_primero()
        )

    @staticmethod
    def especie_repetida(nombre, excluir_pk=None):
        return Especie.objects.filter(nombre__iexact=nombre).exclude(pk=excluir_pk).exists()

    @staticmethod
    def codigo_usado(codigo):
        return Especie.objects.filter(codigo=codigo).exists()

    @staticmethod
    def raza_repetida(especie, nombre, excluir_pk=None):
        """True si la especie ya tiene otra raza con ese nombre (sin importar mayúsculas)."""
        return Raza.objects.filter(especie=especie, nombre__iexact=nombre).exclude(pk=excluir_pk).exists()

    @staticmethod
    def especies_con_razas():
        """Todas las especies (también las desactivadas) con sus razas y cuántas mascotas tiene cada una."""
        razas = Raza.objects.annotate(total_mascotas=Count('mascotas')).mestizo_primero()
        return (
            Especie.objects.annotate(total_mascotas=Count('mascotas', distinct=True),
                                     total_razas=Count('razas', distinct=True))
            .prefetch_related(Prefetch('razas', queryset=razas))
        )

    @staticmethod
    def eliminar(elemento):
        """Borra la especie (con sus razas) o la raza. False si alguna mascota la usa (PROTECT): esa se desactiva."""
        try:
            elemento.delete()
        except ProtectedError:
            return False
        return True
