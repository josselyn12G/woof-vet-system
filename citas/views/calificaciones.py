"""F7: el cliente califica la atención de una cita atendida (RF-21)."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views.generic import FormView

from cuentas.mixins import ClienteRequeridoMixin

from ..forms import CalificarCitaForm
from ..services import AgendaService, CalificacionService
from .agendar import CitaDelClienteMixin

NO_SE_PUEDE_CALIFICAR = 'Solo se puede calificar una cita atendida, y una sola vez.'


class CalificarCitaView(ClienteRequeridoMixin, CitaDelClienteMixin, FormView):
    """
    Estrellas y comentario de una cita de sus mascotas. Una cita de otro cliente responde 404;
    una que todavía no se atendió o ya se calificó vuelve a Mis citas con un aviso.
    """
    form_class = CalificarCitaForm
    template_name = 'citas/calificar.html'

    def get(self, request, *args, **kwargs):
        if not CalificacionService.puede_calificar(self.get_cita()):
            return self.volver_con_aviso()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not CalificacionService.puede_calificar(self.get_cita()):
            return self.volver_con_aviso()
        return super().post(request, *args, **kwargs)

    def volver_con_aviso(self):
        messages.error(self.request, NO_SE_PUEDE_CALIFICAR)
        return redirect('citas:mis_citas')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cita = self.get_cita()
        contexto['cita'] = cita
        contexto['reputacion'] = CalificacionService.resumen_del_veterinario(cita.veterinario, recientes=2)
        return contexto

    def form_valid(self, form):
        cita = self.get_cita()
        try:
            AgendaService.calificar(cita, self.request.user, form.cleaned_data['estrellas'],
                                    form.cleaned_data['comentario'])
        except ValidationError as error:
            # Por ejemplo, se calificó en otra pestaña mientras esta seguía abierta
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f'¡Gracias! Tu opinión sobre la cita de {cita.mascota} quedó guardada.')
        return redirect('citas:mis_citas')
