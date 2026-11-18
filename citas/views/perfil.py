"""F7: el perfil público del veterinario con su reputación (RF-22)."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from cuentas.services import PerfilVeterinarioService

from ..services import CalificacionService, CitaService


class PerfilVeterinarioView(LoginRequiredMixin, TemplateView):
    """
    Especialidad, experiencia, servicios que atiende, calificación promedio, distribución por estrellas y
    opiniones recientes. Lo abre cualquiera con sesión (el cliente lo ve antes de agendar o desde Mis citas);
    un id que no es de un veterinario responde 404.
    """
    template_name = 'citas/perfil_veterinario.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        veterinario = get_object_or_404(CitaService.veterinarios(), pk=self.kwargs['pk'])
        contexto.update({
            'veterinario': veterinario,
            'perfil': PerfilVeterinarioService.de(veterinario),
            'servicios': veterinario.servicios.filter(activo=True),
            'reputacion': CalificacionService.resumen_del_veterinario(veterinario),
        })
        return contexto
