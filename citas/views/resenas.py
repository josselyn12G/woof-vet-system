"""
F7: las opiniones de los clientes vistas desde adentro de la clínica.

- El veterinario ve todas las que recibió (Mis calificaciones), con su promedio y la distribución.
- El administrador ve las de toda la clínica (Reseñas): el desempeño de cada veterinario y cada opinión.
"""
from django.views.generic import ListView

from cuentas.mixins import AdministradorRequeridoMixin, VeterinarioRequeridoMixin

from ..forms import FiltroCalificacionesForm
from ..services import CalificacionService, CitaService


class ListaDeCalificacionesMixin:
    """La lista paginada de opiniones con sus filtros por GET y la consulta para los enlaces de las páginas."""
    context_object_name = 'calificaciones'
    paginate_by = 15

    def crear_filtros(self):
        raise NotImplementedError

    def get_queryset(self):
        self.filtros = self.crear_filtros()
        return CalificacionService.filtradas(**self.datos_filtro())

    def datos_filtro(self):
        return self.filtros.filtros()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        consulta = self.request.GET.copy()
        consulta.pop('page', None)
        contexto.update({
            'filtros': self.filtros,
            'consulta': consulta.urlencode(),
            'hay_filtros': any(self.filtros.filtros().values()),
        })
        return contexto


class MisCalificacionesView(VeterinarioRequeridoMixin, ListaDeCalificacionesMixin, ListView):
    """Las calificaciones que le dieron sus clientes: promedio, distribución y cada opinión (solo las suyas)."""
    template_name = 'citas/mis_calificaciones.html'

    def crear_filtros(self):
        return FiltroCalificacionesForm(self.request.GET)

    def datos_filtro(self):
        # Siempre las del veterinario que entra: nunca las de otro
        return {**self.filtros.filtros(), 'veterinario': self.request.user}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['reputacion'] = CalificacionService.resumen_del_veterinario(self.request.user, recientes=0)
        return contexto


class ResenasView(AdministradorRequeridoMixin, ListaDeCalificacionesMixin, ListView):
    """
    Reseñas de la clínica: cifras generales, el desempeño de cada veterinario según sus calificaciones
    y todas las opiniones, filtrables por veterinario y por estrellas.
    """
    template_name = 'citas/gestion/resenas.html'

    def crear_filtros(self):
        return FiltroCalificacionesForm(self.request.GET, veterinarios=CitaService.veterinarios())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        veterinario = self.filtros.filtros()['veterinario']
        contexto.update({
            # Las cifras y la distribución siguen al veterinario elegido (o a toda la clínica)
            'reputacion': CalificacionService.resumen(CalificacionService.filtradas(veterinario), recientes=0),
            'veterinario': veterinario,
            'desempeno': CalificacionService.desempeno_por_veterinario(CitaService.veterinarios()),
        })
        return contexto
