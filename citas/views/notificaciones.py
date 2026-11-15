"""La campana del panel: los avisos de las citas de quien tiene la sesión (F8)."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from ..services import NotificacionService


class NotificacionesView(LoginRequiredMixin, TemplateView):
    """Sus últimos avisos, los nuevos resaltados. Al abrir la página quedan como leídos."""
    template_name = 'citas/notificaciones.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Primero se leen (con su marca de nuevos) y después se marcan: la página los muestra como estaban
        contexto['notificaciones'] = NotificacionService.de(self.request.user)
        NotificacionService.marcar_leidas(self.request.user)
        contexto['notificaciones_sin_leer'] = 0   # la campana de esta misma página ya sale sin número
        return contexto
