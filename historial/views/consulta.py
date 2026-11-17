"""RF-20: desde una cita atendida, el veterinario registra (o corrige) la consulta, la receta y las vacunas."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from citas.models import EstadoCita
from citas.services import CitaService
from cuentas.mixins import VeterinarioRequeridoMixin

from ..forms import ConsultaForm, RecetaFormSet, VacunasFormSet
from ..services import HistorialService

SOLO_ATENDIDAS = 'La consulta se registra cuando la cita está atendida.'


class RegistrarConsultaView(VeterinarioRequeridoMixin, View):
    """
    Un formulario de la consulta y dos grupos de filas (receta y vacunas) que se guardan juntos.

    Solo las citas del propio veterinario: la de otro responde 404, como si no existiera.
    Una cita que no está atendida vuelve a la agenda con un aviso. Si la cita ya tiene consulta, se edita.
    """
    template_name = 'historial/consulta.html'

    def buscar_cita(self, pk):
        """La cita de la URL entre las del veterinario. Se busca en get/post, después de que el mixin revisó el rol
        (así un cliente recibe 403 y no 404)."""
        self.cita = get_object_or_404(
            CitaService.atendidas_por(self.request.user)
            .select_related('mascota__dueno', 'mascota__especie', 'mascota__raza', 'servicio'),
            pk=pk,
        )
        return self.cita

    def get(self, request, pk):
        if self.buscar_cita(pk).estado != EstadoCita.ATENDIDA:
            return self.volver_con_aviso()
        return self.mostrar(*self.formularios())

    def post(self, request, pk):
        if self.buscar_cita(pk).estado != EstadoCita.ATENDIDA:
            return self.volver_con_aviso()
        consulta_form, recetas, vacunas = self.formularios(request.POST)
        if consulta_form.is_valid() and recetas.is_valid() and vacunas.is_valid():
            nueva = consulta_form.instance.pk is None
            HistorialService.guardar_consulta(consulta_form, recetas, vacunas)
            accion = 'se registró' if nueva else 'se actualizó'
            messages.success(request, f'La consulta de {self.cita.mascota} {accion}.')
            return redirect(self.url_agenda())
        return self.mostrar(consulta_form, recetas, vacunas)

    def formularios(self, datos=None):
        consulta = HistorialService.consulta_de(self.cita)
        kwargs_vacunas = {
            'mascota': self.cita.mascota,
            'veterinario': self.cita.veterinario,
            'fecha': HistorialService.fecha_de_la_cita(self.cita),
        }
        return (
            ConsultaForm(datos, instance=consulta),
            RecetaFormSet(datos, instance=consulta, prefix='recetas'),
            VacunasFormSet(datos, instance=consulta, prefix='vacunas', form_kwargs=kwargs_vacunas),
        )

    def mostrar(self, consulta_form, recetas, vacunas):
        return render(self.request, self.template_name, {
            'cita': self.cita,
            'mascota': self.cita.mascota,
            'form': consulta_form,
            'recetas': recetas,
            'vacunas': vacunas,
            'es_nueva': consulta_form.instance.pk is None,
            'volver': self.url_agenda(),
        })

    def url_agenda(self):
        fecha = timezone.localtime(self.cita.inicio).date()
        return f"{reverse('citas:agenda')}?fecha={fecha.isoformat()}"

    def volver_con_aviso(self):
        messages.error(self.request, SOLO_ATENDIDAS)
        return redirect(self.url_agenda())
