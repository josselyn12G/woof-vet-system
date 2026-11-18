"""El cliente ve la historia clínica y las recetas de sus mascotas (con el seguimiento de cada tratamiento)."""
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
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
            contexto['historial_medico'] = HistorialService.historial_medico(contexto['consultas'], contexto['carnet'])
        contexto['volver'] = reverse('panel:inicio_cliente')
        return contexto


class MisRecetasView(MascotasDelClienteMixin, TemplateView):
    """
    Mis recetas (portada): un tratamiento por consulta, de la más nueva a la más vieja, con su avance;
    arriba el resumen de hoy (qué medicamento toca y si ya se dio). ?mascota=<id> deja solo esa mascota.
    """
    template_name = 'historial/cliente/mis_recetas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        mascotas = self.mascotas()
        elegida = self.elegida(mascotas)
        contexto.update(HistorialService.tratamientos_del_cliente(self.request.user, elegida))
        contexto.update({'mascotas': mascotas, 'mascota_elegida': elegida,
                         'volver': reverse('panel:inicio_cliente')})
        return contexto


class TratamientoView(ClienteRequeridoMixin, TemplateView):
    """
    El tratamiento de una consulta: cada medicamento con su imagen, la dosis del veterinario, la siguiente toma
    y un check por día. Solo consultas de sus mascotas que tienen receta (las demás responden 404).
    """
    template_name = 'historial/cliente/tratamiento.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        datos = HistorialService.tratamientos_del_cliente(self.request.user, consulta=self.kwargs['pk'])
        if not datos['tratamientos']:
            raise Http404('Ese tratamiento no existe o no es de tus mascotas.')
        tratamiento = datos['tratamientos'][0]
        # La tarjeta con la foto (_hc_mascota.html) pregunta por tiene_foto, como en el resto de las fichas
        tratamiento['mascota'].tiene_foto = tratamiento['mascota'].foto is not None
        contexto.update({
            'tratamiento': tratamiento,
            'mascota': tratamiento['mascota'],
            'volver': reverse('historial:mis_recetas') + f"?mascota={tratamiento['mascota'].pk}",
            'subtitulo': (f"{tratamiento['titulo']} del "
                          f"{date_format(timezone.localtime(tratamiento['consulta'].fecha), 'j \\d\\e F')}"
                          f" · {tratamiento['mascota'].nombre}"),
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
