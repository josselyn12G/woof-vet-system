"""Las páginas clínicas del menú del veterinario: Consultas médicas y Vacunación (403 para los demás roles)."""
from django.views.generic import TemplateView

from cuentas.mixins import VeterinarioRequeridoMixin

from ..services import ClinicaDelVeterinarioService


class ConsultasVeterinarioView(VeterinarioRequeridoMixin, TemplateView):
    """Consultas médicas: las citas atendidas que falta registrar y sus últimas consultas, con cifras del mes."""
    template_name = 'historial/veterinario/consultas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(ClinicaDelVeterinarioService.consultas(self.request.user))
        return contexto


class VacunacionVeterinarioView(VeterinarioRequeridoMixin, TemplateView):
    """Vacunación: refuerzos vencidos y próximos de los pacientes y las vacunas que aplicó, con cifras."""
    template_name = 'historial/veterinario/vacunacion.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(ClinicaDelVeterinarioService.vacunacion(self.request.user))
        return contexto
