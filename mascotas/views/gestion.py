"""Gestión de la clínica: todas las mascotas (administrador) y su ficha completa (superadministrador)."""
from django.contrib import messages
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin, BusquedaMixin

from ..mixins import FormularioGestionMixin, MascotaGestionadaMixin
from ..models import Mascota
from ..services import MascotaService


class MascotaGestionListView(AdministradorRequeridoMixin, BusquedaMixin, ListView):
    """Todas las mascotas con su dueño: buscador (mascota, dueño, cédula o teléfono) y filtro por especie."""
    template_name = 'mascotas/gestion/lista.html'
    context_object_name = 'mascotas'
    paginate_by = 12

    def get_queryset(self):
        return MascotaService.de_la_clinica(self.buscar(), self.request.GET.get('especie', ''))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        especie = self.request.GET.get('especie', '')
        resumen = MascotaService.resumen_de_la_clinica()
        contexto.update({
            'buscar': self.buscar(),
            # Solo se marca un filtro que existe (una especie inventada en la URL queda en "Todas")
            'especie_elegida': especie if any(fila['codigo'] == especie for fila in resumen['por_especie']) else '',
            'resumen': resumen,
        })
        return contexto


class MascotaGestionDetailView(AdministradorRequeridoMixin, DetailView):
    """La ficha de cualquier mascota, con su dueño y su historial de citas."""
    template_name = 'mascotas/gestion/detalle.html'
    context_object_name = 'mascota'

    def get_object(self, queryset=None):
        try:
            return MascotaService.ficha_de_la_clinica(self.kwargs['pk'])
        except Mascota.DoesNotExist:
            raise Http404('No existe esa mascota.')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['citas'] = MascotaService.citas_de(self.object)
        return contexto


# ---------------------------------------------------------------------------
# Superadministrador: crea, corrige y elimina la ficha de cualquier mascota (también cambia su dueño)
# ---------------------------------------------------------------------------
class MascotaGestionCreateView(FormularioGestionMixin, CreateView):
    success_message = 'Se registró a %(nombre)s.'

    def get_initial(self):
        # ?dueno=<id> deja elegido al dueño (por ejemplo, desde la búsqueda de un cliente)
        return {'dueno': self.request.GET.get('dueno')}


class MascotaGestionUpdateView(FormularioGestionMixin, UpdateView):
    context_object_name = 'mascota'
    success_message = 'Se guardaron los cambios de %(nombre)s.'

    def get_context_data(self, **kwargs):
        # Si el POST tiene errores, self.object ya trae lo que se escribió: el título usa el nombre guardado
        kwargs['nombre_original'] = MascotaService.nombre_guardado(self.object.pk)
        return super().get_context_data(**kwargs)


class MascotaGestionDeleteView(MascotaGestionadaMixin, DeleteView):
    """GET muestra la confirmación (con cuántas citas se borran con ella); solo el POST borra."""
    template_name = 'mascotas/gestion/confirmar_eliminar.html'
    context_object_name = 'mascota'
    success_url = reverse_lazy('mascotas:gestion')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['total_citas'] = MascotaService.total_citas(self.object)
        return contexto

    def form_valid(self, form):
        messages.success(self.request, f'Se eliminó la ficha de {self.object.nombre}.')
        return super().form_valid(form)
