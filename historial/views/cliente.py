"""El cliente ve la historia clínica y las recetas de sus mascotas (con el seguimiento de cada tratamiento)."""
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView

from cuentas.mixins import ClienteRequeridoMixin
from mascotas.services import MascotaService

from ..models import Prescripcion
from ..services import HistorialService


class MascotasDelClienteMixin(ClienteRequeridoMixin):
    """Las mascotas del cliente y la elegida con ?mascota=<id> (un id ajeno o inventado se ignora)."""

    def mascotas(self):
        return MascotaService.del_dueno(self.request.user).order_by('nombre')

    def elegida(self, mascotas):
        return HistorialService.mascota_elegida(mascotas, self.request.GET.get('mascota'))


class MiHistoriaClinicaView(MascotasDelClienteMixin, TemplateView):
    """
    Historia clínica (menú del cliente): un chip por mascota y la historia de la elegida (la primera si no eligió).
    La línea de tiempo es la misma que la de cada mascota (historial/_historia_columnas.html).
    """
    template_name = 'historial/cliente/mi_historia.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        mascotas = self.mascotas()
        mascota = self.elegida(mascotas) or mascotas.first()
        contexto.update({'mascotas': mascotas, 'mascota': mascota})
        if mascota is not None:
            contexto.update(HistorialService.de_la_mascota(mascota))
            contexto.update(HistorialService.tablero(mascota, contexto['consultas']))
        return contexto


class MisRecetasView(MascotasDelClienteMixin, TemplateView):
    """Mis recetas: todas las de sus mascotas agrupadas por mascota, o solo las de una (?mascota=<id>)."""
    template_name = 'historial/cliente/mis_recetas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        mascotas = self.mascotas()
        elegida = self.elegida(mascotas)
        por_mascota = HistorialService.recetas_del_cliente(self.request.user, elegida)
        contexto.update({
            'mascotas': mascotas,
            'mascota_elegida': elegida,
            'por_mascota': por_mascota,
            'en_curso': sum(1 for _, recetas in por_mascota for receta in recetas if receta.en_curso),
        })
        return contexto


class MarcarDiaView(ClienteRequeridoMixin, View):
    """
    POST: marca (o desmarca) un día del tratamiento de una receta de sus mascotas. La de otra persona responde 404.
    Vuelve a Mis recetas con el mismo filtro de mascota (?volver= solo si es una dirección de este sitio).
    """
    http_method_names = ['post']

    def post(self, request, pk):
        receta = get_object_or_404(Prescripcion.objects.filter(consulta__mascota__dueno=request.user), pk=pk)
        try:
            dia = date.fromisoformat(request.POST.get('dia', ''))
        except ValueError:
            dia = None
        if dia is None:
            messages.error(request, 'Ese día no es válido.')
        else:
            try:
                marcado = HistorialService.marcar_dia(receta, dia)
            except ValidationError as error:
                messages.error(request, error.messages[0])
            else:
                if marcado:
                    messages.success(request, f'Listo: {receta.medicamento} quedó marcado el {dia:%d/%m}.')
        volver = request.POST.get('volver', '')
        if not url_has_allowed_host_and_scheme(volver, allowed_hosts={request.get_host()}):
            volver = reverse('historial:mis_recetas')
        return redirect(f'{volver}#receta-{receta.pk}')
