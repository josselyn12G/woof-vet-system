"""La historia clínica de una mascota, de solo lectura: la ven el dueño, los veterinarios y la clínica."""
from django.http import HttpResponse
from django.urls import reverse
from django.views.generic import DetailView

from cuentas.models import Roles
from mascotas.mixins import MascotaVisiblePorRolMixin

from ..services import HistorialService
from ..services.pdf import generar_pdf, nombre_del_archivo


# A dónde vuelve la flecha de la historia según el rol; el administrador y el superadministrador, a la gestión
VOLVER_POR_ROL = {
    Roles.CLIENTE: lambda mascota: reverse('mascotas:detalle', kwargs={'pk': mascota.pk}),
    Roles.VETERINARIO: lambda mascota: reverse('citas:pacientes'),
}


def volver_a_la_gestion(mascota):
    return reverse('mascotas:gestion_detalle', kwargs={'pk': mascota.pk})


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
        contexto.update(HistorialService.tablero(self.object, contexto['consultas']))   # las tarjetas
        contexto['historial_medico'] = HistorialService.historial_medico(contexto['consultas'], contexto['carnet'])
        contexto['volver'] = self.url_volver()
        return contexto

    def url_volver(self):
        """La flecha de volver lleva a la pantalla desde la que entra cada rol."""
        return VOLVER_POR_ROL.get(self.request.user.rol, volver_a_la_gestion)(self.object)


class HistoriaPdfView(MascotaVisiblePorRolMixin, DetailView):
    """La misma historia en PDF, con el formato de Woof. La descargan los mismos que pueden verla (404 si no)."""

    def get(self, request, *args, **kwargs):
        mascota = self.get_object()
        respuesta = HttpResponse(generar_pdf(mascota), content_type='application/pdf')
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre_del_archivo(mascota)}"'
        return respuesta

