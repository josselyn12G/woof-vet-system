"""El catálogo de vacunas (administrador y superadministrador): listar, crear, editar y desactivar."""
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin, BusquedaMixin

from ..forms import VacunaForm
from ..models import Vacuna
from ..services import VacunaCatalogoService


class VacunaListView(AdministradorRequeridoMixin, BusquedaMixin, ListView):
    """Todas las vacunas, también las desactivadas: buscador (nombre o especie) y filtro por estado."""
    template_name = 'historial/vacunas/lista.html'
    context_object_name = 'vacunas'
    paginate_by = 20

    def get_queryset(self):
        return VacunaCatalogoService.buscar(self.buscar(), self.request.GET.get('estado', ''))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.buscar()
        contexto['estado_elegido'] = self.request.GET.get('estado', '')
        return contexto


class VacunaFormularioMixin(AdministradorRequeridoMixin, SuccessMessageMixin):
    model = Vacuna
    form_class = VacunaForm
    template_name = 'historial/vacunas/formulario.html'
    success_url = reverse_lazy('historial:vacunas')


class VacunaCreateView(VacunaFormularioMixin, CreateView):
    success_message = 'Se agregó la vacuna %(nombre)s.'


class VacunaUpdateView(VacunaFormularioMixin, UpdateView):
    context_object_name = 'vacuna'
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class VacunaEstadoView(AdministradorRequeridoMixin, View):
    """Activa o desactiva una vacuna. Solo POST: un enlace no debe cambiar datos."""
    http_method_names = ['post']

    def post(self, request, pk):
        vacuna = get_object_or_404(VacunaCatalogoService.todas(), pk=pk)
        if VacunaCatalogoService.alternar_estado(vacuna):
            messages.success(request, f'{vacuna} vuelve a ofrecerse al registrar una consulta.')
        else:
            messages.success(request, f'{vacuna} se desactivó: ya no se ofrece, pero los carnets la conservan.')
        return redirect('historial:vacunas')
