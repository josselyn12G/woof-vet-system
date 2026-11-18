"""Core del veterinario: su agenda del día, cerrar cada cita y sus pacientes."""
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from cuentas.mixins import VeterinarioRequeridoMixin
from mascotas.services import MascotaService

from ..services import AgendaService, CitaService
from ..services.horarios import leer_fecha


class AgendaVeterinarioView(VeterinarioRequeridoMixin, TemplateView):
    """
    Las citas del veterinario en un día (?fecha=2026-11-02; por defecto hoy), en orden de hora.
    Desde aquí marca cada cita como atendida o no asistió.
    """
    template_name = 'citas/agenda.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        fecha = leer_fecha(self.request.GET.get('fecha')) or timezone.localdate()   # una fecha inventada vuelve a hoy
        contexto.update(CitaService.agenda_del_dia(self.request.user, fecha))
        contexto.update({
            'fecha': fecha,
            'hoy': timezone.localdate(),
            'anterior': fecha - timedelta(days=1),
            'siguiente': fecha + timedelta(days=1),
            'ahora': timezone.now(),
        })
        return contexto


class ResultadoCitaView(VeterinarioRequeridoMixin, View):
    """Marca una cita como atendida o no asistió (POST). Solo las citas del propio veterinario: las de otro, 404."""

    def post(self, request, pk):
        cita = get_object_or_404(CitaService.atendidas_por(request.user), pk=pk)
        try:
            AgendaService.registrar_resultado(cita, request.POST.get('estado'))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'La cita de {cita.mascota} quedó como «{cita.get_estado_display().lower()}».')
        fecha = timezone.localtime(cita.inicio).date()
        return redirect(f"{reverse('citas:agenda')}?fecha={fecha.isoformat()}")


class PacientesView(VeterinarioRequeridoMixin, ListView):
    """
    Pacientes del veterinario: una tarjeta por mascota con su dueño asociado.
    Busca por el nombre de la mascota o por nombre, usuario, correo, cédula o teléfono del dueño.
    Con ?mios=1 deja solo las mascotas que ya tuvieron o tienen cita con él.
    """
    template_name = 'citas/pacientes.html'
    context_object_name = 'mascotas'
    paginate_by = 12

    def get_queryset(self):
        return MascotaService.pacientes(
            self.request.user, self.request.GET.get('q', '').strip(), bool(self.request.GET.get('mios')),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.request.GET.get('q', '').strip()
        contexto['solo_mios'] = bool(self.request.GET.get('mios'))
        return contexto
