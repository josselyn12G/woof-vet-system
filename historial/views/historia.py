"""La historia clínica de una mascota, de solo lectura: la ven el dueño, los veterinarios y la clínica."""
from django.urls import reverse
from django.views.generic import DetailView

from mascotas.mixins import MascotaVisiblePorRolMixin

from ..services import HistorialService


class HistoriaClinicaView(MascotaVisiblePorRolMixin, DetailView):
    """
    Una sola plantilla con tres entradas según el rol:
    el cliente llega desde el detalle de su mascota (404 con una ajena), el veterinario desde Pacientes
    y el administrador o el superadministrador desde la gestión de mascotas. Sin sesión va al login.
    """
    template_name = 'historial/historia.html'
    context_object_name = 'mascota'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(HistorialService.de_la_mascota(self.object))   # consultas y vacunas
        contexto['volver'] = self.url_volver()
        return contexto

    def url_volver(self):
        """La flecha de volver lleva a la pantalla desde la que entra cada rol."""
        usuario = self.request.user
        if usuario.es_cliente:
            return reverse('mascotas:detalle', kwargs={'pk': self.object.pk})
        if usuario.es_veterinario:
            return reverse('citas:pacientes')
        return reverse('mascotas:gestion_detalle', kwargs={'pk': self.object.pk})
