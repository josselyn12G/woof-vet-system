"""Core del cliente: agendar una cita (con su calendario en JSON), ver Mis citas y cancelar."""
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, TemplateView

from cuentas.mixins import ClienteRequeridoMixin
from mascotas.services import MascotaService

from ..forms import AgendarCitaForm
from ..services import VISTAS_CITAS, AgendaService, CitaService, ServicioService
from ..services.formato import datos_de_confirmacion
from ..services.horarios import leer_fecha


class AgendarCitaView(ClienteRequeridoMixin, FormView):
    """
    Formulario para agendar (HU-27). La vista no decide si el turno está libre:
    se lo pide a AgendaService, que valida y guarda dentro de una transacción.
    """
    form_class = AgendarCitaForm
    template_name = 'citas/agendar.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente'] = self.request.user
        return kwargs

    def get_initial(self):
        # Desde la ficha de una mascota se llega con ?mascota=<id> y queda elegida
        return {'mascota': self.request.GET.get('mascota')}

    def form_valid(self, form):
        datos = form.cleaned_data
        try:
            cita = AgendaService.agendar(
                mascota=datos['mascota'], veterinario=datos['veterinario'], servicio=datos['servicio'],
                inicio=datos['inicio'], motivo=datos['motivo'],
            )
        except ValidationError as error:
            # El mensaje del Core (turno ocupado, servicio inactivo...) se muestra arriba del formulario
            form.add_error(None, error)
            return self.form_invalid(form)

        # La confirmación se muestra como pop-up: con fetch (desde el pop-up de Mis citas) van los datos en JSON;
        # sin JavaScript, como mensaje que Mis citas abre en un pop-up al cargar
        confirmacion = datos_de_confirmacion(cita)
        if es_fetch(self.request):
            return JsonResponse(confirmacion)
        # extra_tags="agendada": Mis citas muestra este mensaje en el pop-up de confirmación (los demás, como avisos)
        messages.success(
            self.request, f"{confirmacion['titulo']} {confirmacion['detalle']}, {confirmacion['cuando']}.",
            extra_tags='agendada',
        )
        return redirect('citas:mis_citas')

    def form_invalid(self, form):
        # Desde el pop-up, con errores se devuelve solo la reserva (el parcial) para reemplazarla ahí mismo
        if es_fetch(self.request):
            return render(self.request, 'citas/_reserva.html', {'form': form})
        return super().form_invalid(form)


def es_fetch(request):
    """True si el pedido viene de fetch (agendar.js manda la cabecera X-Requested-With: fetch)."""
    return request.headers.get('X-Requested-With') == 'fetch'



def servicio_pedido(request):
    """El servicio activo de ?servicio=<id>, o None."""
    return ServicioService.activo(request.GET.get('servicio'))


class TurnosDelDiaView(ClienteRequeridoMixin, View):
    """
    Devuelve en JSON las horas libres de un servicio en una fecha, agrupadas por veterinario.
    La pide agendar.js al tocar un día; la regla es la misma que usa agendar().
    """

    def get(self, request):
        servicio = servicio_pedido(request)
        fecha = leer_fecha(request.GET.get('fecha'))
        if not (servicio and fecha):
            return JsonResponse({'turnos': []})

        turnos = [
            {
                'veterinario': veterinario.pk,
                'nombre': veterinario.get_full_name() or veterinario.username,
                'horas': [f'{timezone.localtime(inicio):%H:%M}' for inicio in espacios],
            }
            for veterinario, espacios in AgendaService.turnos_del_dia(servicio, fecha)
        ]
        return JsonResponse({'turnos': turnos})


class DiasDisponiblesView(ClienteRequeridoMixin, View):
    """Devuelve en JSON los días del mes (?mes=2026-11) en que el servicio tiene turnos libres; el calendario los marca."""

    def get(self, request):
        servicio = servicio_pedido(request)
        try:
            anio, mes = (int(parte) for parte in request.GET.get('mes', '').split('-'))
            date(anio, mes, 1)
        except ValueError:
            anio = None

        if not (servicio and anio):
            return JsonResponse({'dias': []})
        dias = AgendaService.dias_del_servicio(servicio, anio, mes)
        return JsonResponse({'dias': [dia.isoformat() for dia in dias]})


class MisCitasView(ClienteRequeridoMixin, TemplateView):
    """
    Las citas de las mascotas del cliente en tres pestañas (?vista=proximas|pasadas|canceladas),
    agrupadas por día; al costado, su próxima cita, la última y sus mascotas.
    """
    template_name = 'citas/mis_citas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vista = self.request.GET.get('vista', 'proximas')
        if vista not in VISTAS_CITAS:   # una pestaña inventada en la URL vuelve a Próximas
            vista = 'proximas'

        contexto.update(CitaService.del_cliente(self.request.user, vista))
        contexto.update({
            # La reserva del pop-up "Agendar cita" (el mismo formulario de AgendarCitaView)
            'form': AgendarCitaForm(cliente=self.request.user),
            'abrir_agendar': 'agendar' in self.request.GET,   # ?agendar abre el pop-up al cargar (desde el inicio)
            'vista': vista,
            'mascotas': MascotaService.del_dueno(self.request.user).order_by('nombre'),
            'hoy': timezone.localdate(),
            'ahora': timezone.now(),
        })
        return contexto


class CancelarCitaView(ClienteRequeridoMixin, View):
    """Cancela una cita por POST. Una cita de otro cliente responde 404, como si no existiera."""

    def post(self, request, pk):
        cita = get_object_or_404(CitaService.de_las_mascotas_de(request.user), pk=pk)
        try:
            AgendaService.cancelar(cita)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'Se canceló la cita de {cita.mascota}. El horario quedó libre.')
        return redirect('citas:mis_citas')
