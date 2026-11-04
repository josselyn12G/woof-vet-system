from django.db.models import Count, Prefetch, ProtectedError

from mascotas.models import Especie, Raza


class CatalogoService:
    """El catálogo de especies y razas que se ofrece al registrar una mascota (lo gestiona el superadministrador)."""

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
