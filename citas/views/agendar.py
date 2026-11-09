"""Core del cliente: agendar una cita (con su calendario en JSON), ver Mis citas, cancelar y reprogramar."""
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

from ..forms import AgendarCitaForm, ReprogramarCitaForm
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



def mes_pedido(request):
    """(anio, mes) de ?mes=2026-11, o None si falta o no es válido."""
    try:
        anio, mes = (int(parte) for parte in request.GET.get('mes', '').split('-'))
        date(anio, mes, 1)
    except ValueError:
        return None
    return anio, mes


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
        mes = mes_pedido(request)
        if not (servicio and mes):
            return JsonResponse({'dias': []})
        dias = AgendaService.dias_del_servicio(servicio, *mes)
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


class CitaDelClienteMixin:
    """La cita de la URL, solo si es de una mascota del cliente (si no, 404 como si no existiera)."""

    def get_cita(self):
        if not hasattr(self, 'cita'):
            self.cita = get_object_or_404(
                CitaService.de_las_mascotas_de(self.request.user).select_related('servicio', 'veterinario'),
                pk=self.kwargs['pk'],
            )
        return self.cita


class ReprogramarCitaView(ClienteRequeridoMixin, CitaDelClienteMixin, FormView):
    """
    Cambia el día y la hora de una cita (mismo veterinario y servicio). La vista no mueve nada:
    AgendaService.reprogramar() lo hace en una sola transacción y, si falla, la cita sigue en su hora.
    """
    form_class = ReprogramarCitaForm
    template_name = 'citas/reprogramar.html'

    def get(self, request, *args, **kwargs):
        if not AgendaService.se_puede_reprogramar(self.get_cita()):
            messages.error(request, 'Solo se puede reprogramar una cita confirmada que todavía no empieza.')
            return redirect('citas:mis_citas')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['cita'] = self.get_cita()
        return contexto

    def form_valid(self, form):
        cita = self.get_cita()
        anterior = timezone.localtime(cita.inicio)
        try:
            cita = AgendaService.reprogramar(cita, form.cleaned_data['inicio'])
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        nueva = timezone.localtime(cita.inicio)
        messages.success(
            self.request,
            f'La cita de {cita.mascota} pasó del {anterior:%d/%m} a las {anterior:%H:%M} '
            f'al {nueva:%d/%m} a las {nueva:%H:%M}.',
        )
        return redirect('citas:mis_citas')


class ReprogramarDiasView(ClienteRequeridoMixin, CitaDelClienteMixin, View):
    """Días del mes (?mes=2026-11) con turnos libres para mover la cita; el calendario los marca."""

    def get(self, request, pk):
        mes = mes_pedido(request)
        cita = self.get_cita()
        if not (mes and AgendaService.se_puede_reprogramar(cita)):
            return JsonResponse({'dias': []})
        dias = AgendaService.dias_para_reprogramar(cita, *mes)
        return JsonResponse({'dias': [dia.isoformat() for dia in dias]})


class ReprogramarHorasView(ClienteRequeridoMixin, CitaDelClienteMixin, View):
    """Horas libres de un día (?fecha=2026-11-20) para mover la cita, sin su hora actual."""

    def get(self, request, pk):
        fecha = leer_fecha(request.GET.get('fecha'))
        cita = self.get_cita()
        if not (fecha and AgendaService.se_puede_reprogramar(cita)):
            return JsonResponse({'horas': []})
        horas = AgendaService.horas_para_reprogramar(cita, fecha)
        return JsonResponse({'horas': [f'{timezone.localtime(inicio):%H:%M}' for inicio in horas]})
