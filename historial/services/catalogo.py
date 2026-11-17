from django.db.models import Count, Q

from historial.models import Vacuna
from mascotas.models import Especie


class VacunaCatalogoService:
    """
    El catálogo de vacunas que lo gestiona el administrador, como el catálogo de especies.
    Una vacuna no se borra: se desactiva, deja de ofrecerse al registrar y el carnet la sigue mostrando.
    """

    @staticmethod
    def todas():
        return Vacuna.objects.select_related('especie')

    @staticmethod
    def buscar(texto='', estado=''):
        """
        Todas las vacunas con cuántas veces se aplicaron, para la lista del administrador.
        estado es 'activas' o 'inactivas'; otro valor no filtra.
        """
        vacunas = VacunaCatalogoService.todas().annotate(total_aplicaciones=Count('aplicaciones'))
        if texto:
            vacunas = vacunas.filter(Q(nombre__icontains=texto) | Q(especie__nombre__icontains=texto))
        if estado == 'activas':
            vacunas = vacunas.filter(activa=True)
        elif estado == 'inactivas':
            vacunas = vacunas.filter(activa=False)
        return vacunas.order_by('nombre', 'especie__nombre')

    @staticmethod
    def especies_para_elegir(actual_pk=None):
        """Las especies activas para el formulario; al editar, también la que ya tiene la vacuna."""
        return Especie.objects.filter(Q(activa=True) | Q(pk=actual_pk))

    @staticmethod
    def nombre_repetido(nombre, especie, excluir_pk=None):
        """True si ya hay otra vacuna con ese nombre para esa especie (o para todas, si especie es None)."""
        return (
            Vacuna.objects.filter(nombre__iexact=nombre, especie=especie)
            .exclude(pk=excluir_pk)
            .exists()
        )

    @staticmethod
    def alternar_estado(vacuna):
        """Activa la vacuna si estaba desactivada y al revés. Devuelve cómo quedó (True = activa)."""
        vacuna.activa = not vacuna.activa
        vacuna.save(update_fields=['activa'])
        return vacuna.activa
