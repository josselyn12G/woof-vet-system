"""Gestión de la clínica (administrador y superadministrador): todas las citas y los horarios."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from cuentas.mixins import AdministradorRequeridoMixin

from ..forms import FiltroCitasForm
from ..services import VISTAS_GESTION, AgendaService, CitaService, HorarioService
from ..services.horarios import semana_pedida


class GestionCitasView(AdministradorRequeridoMixin, ListView):
    """
    Todas las citas de la clínica en pestañas (?vista=proximas|hoy|pasadas|todas), con buscador
    y filtros por estado, veterinario y servicio. Desde aquí se cancela una cita confirmada.
    """
    template_name = 'citas/gestion/citas.html'
    context_object_name = 'citas'
    paginate_by = 20

    def vista(self):
        vista = self.request.GET.get('vista', 'proximas')
        return vista if vista in VISTAS_GESTION else 'proximas'

    def get_queryset(self):
        self.filtros = FiltroCitasForm(self.request.GET, veterinarios=CitaService.veterinarios())
        return CitaService.de_la_clinica(self.vista(), **self.filtros.filtros())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Los filtros sin la página, para que los enlaces de las páginas los conserven
        consulta = self.request.GET.copy()
        consulta.pop('page', None)
        sin_vista = consulta.copy()
        sin_vista.pop('vista', None)
        contexto.update({
            'filtros': self.filtros,
            'vista': self.vista(),
            'vistas': VISTAS_GESTION.items(),
            'resumen': CitaService.resumen_de_la_clinica(),
            'consulta': consulta.urlencode(),
            'consulta_sin_vista': sin_vista.urlencode(),
            'hay_filtros': any(self.filtros.filtros().values()),
            'ahora': timezone.now(),
        })
        return contexto


class GestionCancelarCitaView(AdministradorRequeridoMixin, View):
    """El administrador cancela una cita confirmada que todavía no empieza (POST); el turno vuelve a quedar libre."""
    http_method_names = ['post']

    def post(self, request, pk):
        cita = get_object_or_404(CitaService.todas(), pk=pk)
        try:
            AgendaService.cancelar(cita)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'Se canceló la cita de {cita.mascota}. El horario quedó libre.')
        destino = request.POST.get('volver', '')
        # Solo se vuelve a la propia gestión de citas (nunca a una URL de afuera)
        if not destino.startswith(reverse('citas:gestion_citas')):
            destino = reverse('citas:gestion_citas')
        return redirect(destino)


class GestionHorariosView(AdministradorRequeridoMixin, TemplateView):
    """La semana de toda la clínica: una fila por veterinario y una columna por día, con sus bloques."""
    template_name = 'citas/gestion/horarios.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(HorarioService.semana_de_la_clinica(semana_pedida(self.request.GET.get('semana'))))
        return contexto
