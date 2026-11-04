from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from cuentas.mixins import (
    AdministradorRequeridoMixin, ClienteRequeridoMixin, SuperadminRequeridoMixin, VeterinarioRequeridoMixin,
)
from cuentas.models import Roles
from mascotas.services import MascotaService

from .forms import AgendarCitaForm, FiltroCitasForm, HorarioForm, MisServiciosForm, ServicioForm
from .models import Cita, HorarioVeterinario, Servicio
from .services import (
    VISTAS_CITAS, VISTAS_GESTION, AgendaService, CitaService, HorarioService, ServicioService,
)
from .services.horarios import leer_fecha, lunes_de, semana_pedida


def plural(cantidad, palabra):
    return f'{cantidad} {palabra}{"s" if cantidad != 1 else ""}'


class ServicioListView(AdministradorRequeridoMixin, ListView):
    """Catálogo de servicios de la clínica (HU-25, RF-04): buscador y filtro por estado."""
    template_name = 'citas/servicios/lista.html'
    context_object_name = 'servicios'
    paginate_by = 20

    def get_queryset(self):
        return ServicioService.buscar(self.request.GET.get('q', '').strip(), self.request.GET.get('estado', ''))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.request.GET.get('q', '').strip()
        contexto['estado_elegido'] = self.request.GET.get('estado', '')
        return contexto


class ServicioCreateView(AdministradorRequeridoMixin, SuccessMessageMixin, CreateView):
    model = Servicio
    form_class = ServicioForm
    template_name = 'citas/servicios/formulario.html'
    success_url = reverse_lazy('citas:servicios')
    success_message = 'El servicio %(nombre)s se creó.'


class ServicioUpdateView(AdministradorRequeridoMixin, SuccessMessageMixin, UpdateView):
    model = Servicio
    form_class = ServicioForm
    template_name = 'citas/servicios/formulario.html'
    context_object_name = 'servicio'
    success_url = reverse_lazy('citas:servicios')
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class ServicioEstadoView(AdministradorRequeridoMixin, View):
    """Activa o desactiva un servicio (RF-06). Solo POST: un enlace no debe cambiar datos."""
    http_method_names = ['post']

    def post(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk)
        if ServicioService.alternar_estado(servicio):
            messages.success(request, f'{servicio.nombre} vuelve a ofrecerse al agendar.')
        else:
            messages.success(request, f'{servicio.nombre} se desactivó: ya no se ofrece al agendar.')
        return redirect('citas:servicios')


class ServicioDeleteView(AdministradorRequeridoMixin, DeleteView):
    """GET muestra la confirmación; el POST borra. Un servicio con citas no se borra (Cita.servicio es PROTECT):
    se ofrece desactivarlo para que las citas pasadas lo conserven."""
    model = Servicio
    template_name = 'citas/servicios/confirmar_eliminar.html'
    context_object_name = 'servicio'
    success_url = reverse_lazy('citas:servicios')

    def form_valid(self, form):
        if not ServicioService.eliminar(self.object):
            messages.error(
                self.request,
                f'{self.object.nombre} tiene citas registradas y no se puede eliminar. Desactívalo en su lugar.',
            )
            return redirect('citas:servicios')
        messages.success(self.request, f'{self.object.nombre} se eliminó.')
        return redirect(self.success_url)


# ---------- Mi horario (veterinario): HU-26, RF-07 a RF-10 ----------
# Las mismas vistas sirven al superadministrador para editar el horario de cualquier veterinario
# (desde Horarios): solo cambian de quién es el horario, a qué URLs van los formularios y los textos.

class HorarioDelVeterinarioMixin(VeterinarioRequeridoMixin):
    """Solo el veterinario entra (403 para los demás) y solo ve sus bloques: el de otro veterinario
    no está en la consulta, así que get_object() responde 404."""
    model = HorarioVeterinario
    # Nombre de cada URL del horario (las de la gestión llevan además el id del veterinario)
    rutas = {'semana': 'citas:horario', 'editar': 'citas:horario_editar', 'eliminar': 'citas:horario_eliminar',
             'copiar': 'citas:horario_copiar', 'servicios': 'citas:mis_servicios'}
    el_horario = 'tu horario'   # para los mensajes: "se cruzaban con tu horario"

    @property
    def veterinario(self):
        return self.request.user

    def url(self, nombre, *args):
        return reverse(self.rutas[nombre], args=args)

    def url_semana(self, fecha):
        return f"{self.url('semana')}?semana={lunes_de(fecha).isoformat()}"

    def texto_servicios(self, cantidad):
        return f'Ahora atiendes {plural(cantidad, "servicio")}.'

    def get_queryset(self):
        return HorarioService.del_veterinario(self.veterinario)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['vet_gestionado'] = None   # la plantilla dice "Mi horario"
        return contexto


class HorarioGestionadoMixin(SuperadminRequeridoMixin):
    """El superadministrador edita el horario del veterinario de la URL (403 para los demás roles;
    404 si el id no es de un veterinario). Un bloque de otro veterinario tampoco está en la consulta."""
    rutas = {'semana': 'citas:gestion_horario', 'editar': 'citas:gestion_horario_editar',
             'eliminar': 'citas:gestion_horario_eliminar', 'copiar': 'citas:gestion_horario_copiar',
             'servicios': 'citas:gestion_horario_servicios'}
    el_horario = 'su horario'

    @cached_property
    def veterinario(self):
        return get_object_or_404(get_user_model(), pk=self.kwargs['vet'], rol=Roles.VETERINARIO)

    def url(self, nombre, *args):
        return reverse(self.rutas[nombre], args=[self.veterinario.pk, *args])

    def texto_servicios(self, cantidad):
        return f'{self.veterinario} ahora atiende {plural(cantidad, "servicio")}.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['vet_gestionado'] = self.veterinario
        return contexto


class MiHorarioView(HorarioDelVeterinarioMixin, SuccessMessageMixin, CreateView):
    """La semana en columnas (un día por columna), el formulario "Nuevo bloque" y los servicios que atiende."""
    form_class = HorarioForm
    template_name = 'citas/horario/semana.html'
    success_message = 'Se agregó el bloque del %(fecha)s de %(hora_inicio)s a %(hora_fin)s.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # El veterinario no va en el formulario (es el de la sesión o el de la URL); va antes de validar
        # para revisar los cruces
        kwargs['instance'] = HorarioVeterinario(veterinario=self.veterinario)
        return kwargs

    def get_initial(self):
        # ?fecha= llega desde el "+" de un día de la grilla; si no, hoy o el lunes de la semana elegida
        lunes = semana_pedida(self.request.GET.get('semana'))
        return {'fecha': HorarioService.fecha_sugerida(lunes, leer_fecha(self.request.GET.get('fecha')))}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        lunes = semana_pedida(self.request.GET.get('semana'))
        contexto.update(HorarioService.semana_del_veterinario(self.veterinario, lunes))
        for dia in contexto['dias']:
            for bloque in dia['bloques']:
                bloque.url_editar = self.url('editar', bloque.pk)
                bloque.url_eliminar = self.url('eliminar', bloque.pk)
        contexto['rutas'] = {nombre: self.url(nombre) for nombre in ('semana', 'copiar', 'servicios')}
        contexto['servicios_form'] = MisServiciosForm(
            initial={'servicios': self.veterinario.servicios.filter(activo=True)},
        )
        return contexto

    def get_success_message(self, cleaned_data):
        return self.success_message % {
            'fecha': cleaned_data['fecha'].strftime('%d/%m'),
            'hora_inicio': cleaned_data['hora_inicio'].strftime('%H:%M'),
            'hora_fin': cleaned_data['hora_fin'].strftime('%H:%M'),
        }

    def get_success_url(self):
        return self.url_semana(self.object.fecha)


class HorarioEditarView(HorarioDelVeterinarioMixin, SuccessMessageMixin, UpdateView):
    form_class = HorarioForm
    template_name = 'citas/horario/editar.html'
    context_object_name = 'bloque'
    success_message = 'Se guardaron los cambios del bloque.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Con errores, self.object trae la fecha que se escribió: "Cancelar" vuelve a la semana guardada
        contexto['volver'] = self.url_semana(HorarioVeterinario.objects.get(pk=self.object.pk).fecha)
        return contexto

    def get_success_url(self):
        return self.url_semana(self.object.fecha)


class HorarioEliminarView(HorarioDelVeterinarioMixin, DeleteView):
    """Solo POST (el botón pide confirmación en el navegador). Cuando exista Cita, aquí se debe impedir
    quitar un bloque que ya tiene citas reservadas (HU-26)."""
    http_method_names = ['post']

    def form_valid(self, form):
        fecha = self.object.fecha
        self.object.delete()
        messages.success(self.request, f'Se quitó el bloque de {self.el_horario}.')
        return redirect(self.url_semana(fecha))


class CopiarSemanaView(HorarioDelVeterinarioMixin, View):
    """Copia los bloques de la semana anterior en la semana elegida (HU-26). Se saltan los días que ya
    pasaron y los bloques que se cruzarían con otros que ya están cargados."""
    http_method_names = ['post']

    def post(self, request, **kwargs):
        lunes = semana_pedida(request.POST.get('semana'))
        try:
            copiados, omitidos = HorarioService.copiar_semana(self.veterinario, lunes)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect(self.url_semana(lunes))

        if copiados:
            texto = f'Se copiaron {plural(copiados, "bloque")} de la semana anterior.'
            if omitidos:
                texto += f' {omitidos} no se copiaron porque el día ya pasó o se cruzaban con {self.el_horario}.'
            messages.success(request, texto)
        else:
            messages.error(request,
                           f'No se copió ningún bloque: los días ya pasaron o se cruzaban con {self.el_horario}.')
        return redirect(self.url_semana(lunes))


class MisServiciosView(HorarioDelVeterinarioMixin, View):
    """Guarda los servicios que atiende el veterinario: solo aparece al agendar los que marque."""
    http_method_names = ['post']

    def post(self, request, **kwargs):
        formulario = MisServiciosForm(request.POST)
        destino = self.url_semana(semana_pedida(request.POST.get('semana')))
        if not formulario.is_valid():
            messages.error(request, 'Elige servicios de la lista.')
            return redirect(destino)
        cantidad = HorarioService.guardar_servicios(self.veterinario, formulario.cleaned_data['servicios'])
        messages.success(request, self.texto_servicios(cantidad))
        return redirect(destino)


# El superadministrador, en el horario de un veterinario (Horarios > el veterinario)
class GestionHorarioView(HorarioGestionadoMixin, MiHorarioView):
    pass


class GestionHorarioEditarView(HorarioGestionadoMixin, HorarioEditarView):
    pass


class GestionHorarioEliminarView(HorarioGestionadoMixin, HorarioEliminarView):
    pass


class GestionCopiarSemanaView(HorarioGestionadoMixin, CopiarSemanaView):
    pass


class GestionServiciosVeterinarioView(HorarioGestionadoMixin, MisServiciosView):
    pass


# ---------------------------------------------------------------------------
# Core: el cliente agenda, ve y cancela sus citas
# ---------------------------------------------------------------------------
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


def datos_de_confirmacion(cita):
    """Lo que se ve en el pop-up de "cita agendada": mascota, servicio, día, hora y doctor."""
    inicio = timezone.localtime(cita.inicio)
    return {
        'titulo': f'{cita.mascota} tiene cita.',
        'detalle': f'{cita.servicio} con {cita.veterinario.get_full_name() or cita.veterinario.username}',
        'cuando': date_format(inicio, r'l j \d\e F, H:i'),
    }


def servicio_pedido(request):
    """El servicio activo de ?servicio=<id>, o None."""
    return Servicio.objects.filter(pk=request.GET.get('servicio') or 0, activo=True).first()


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
        cita = get_object_or_404(Cita, pk=pk, mascota__dueno=request.user)
        try:
            AgendaService.cancelar(cita)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'Se canceló la cita de {cita.mascota}. El horario quedó libre.')
        return redirect('citas:mis_citas')


# ---------------------------------------------------------------------------
# Core: la agenda del veterinario
# ---------------------------------------------------------------------------
class AgendaVeterinarioView(VeterinarioRequeridoMixin, TemplateView):
    """
    Las citas del veterinario en un día (?fecha=2026-11-02; por defecto hoy), en orden de hora.
    Desde aquí marca cada cita como atendida o no asistió.
    """
    template_name = 'citas/agenda.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        fecha = leer_fecha(self.request.GET.get('fecha')) or timezone.localdate()   # una fecha inventada vuelve a hoy
        contexto.update(CitaService.agenda_del_dia(self.request.user, fecha))
        contexto.update({
            'fecha': fecha,
            'hoy': timezone.localdate(),
            'anterior': fecha - timedelta(days=1),
            'siguiente': fecha + timedelta(days=1),
            'ahora': timezone.now(),
        })
        return contexto


class ResultadoCitaView(VeterinarioRequeridoMixin, View):
    """Marca una cita como atendida o no asistió (POST). Solo las citas del propio veterinario: las de otro, 404."""

    def post(self, request, pk):
        cita = get_object_or_404(Cita, pk=pk, veterinario=request.user)
        try:
            AgendaService.registrar_resultado(cita, request.POST.get('estado'))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'La cita de {cita.mascota} quedó como «{cita.get_estado_display().lower()}».')
        fecha = timezone.localtime(cita.inicio).date()
        return redirect(f"{reverse('citas:agenda')}?fecha={fecha.isoformat()}")


class PacientesView(VeterinarioRequeridoMixin, ListView):
    """
    Pacientes del veterinario: una tarjeta por mascota con su dueño asociado.
    Busca por el nombre de la mascota o por nombre, usuario, correo, cédula o teléfono del dueño.
    Con ?mios=1 deja solo las mascotas que ya tuvieron o tienen cita con él.
    """
    template_name = 'citas/pacientes.html'
    context_object_name = 'mascotas'
    paginate_by = 12

    def get_queryset(self):
        return MascotaService.pacientes(
            self.request.user, self.request.GET.get('q', '').strip(), bool(self.request.GET.get('mios')),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.request.GET.get('q', '').strip()
        contexto['solo_mios'] = bool(self.request.GET.get('mios'))
        return contexto


# ---------------------------------------------------------------------------
# Gestión de la clínica (administrador y superadministrador): citas y horarios
# ---------------------------------------------------------------------------
class GestionCitasView(AdministradorRequeridoMixin, ListView):
    """
    Todas las citas de la clínica en pestañas (?vista=proximas|hoy|pasadas|todas), con buscador
    y filtros por estado, veterinario y servicio. Desde aquí se cancela una cita confirmada.
    """
    template_name = 'citas/gestion/citas.html'
    context_object_name = 'citas'
    paginate_by = 20

    def vista(self):
        vista = self.request.GET.get('vista', 'proximas')
        return vista if vista in VISTAS_GESTION else 'proximas'

    def get_queryset(self):
        self.filtros = FiltroCitasForm(self.request.GET, veterinarios=CitaService.veterinarios())
        return CitaService.de_la_clinica(self.vista(), **self.filtros.filtros())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Los filtros sin la página, para que los enlaces de las páginas los conserven
        consulta = self.request.GET.copy()
        consulta.pop('page', None)
        sin_vista = consulta.copy()
        sin_vista.pop('vista', None)
        contexto.update({
            'filtros': self.filtros,
            'vista': self.vista(),
            'vistas': VISTAS_GESTION.items(),
            'resumen': CitaService.resumen_de_la_clinica(),
            'consulta': consulta.urlencode(),
            'consulta_sin_vista': sin_vista.urlencode(),
            'hay_filtros': any(self.filtros.filtros().values()),
            'ahora': timezone.now(),
        })
        return contexto


class GestionCancelarCitaView(AdministradorRequeridoMixin, View):
    """El administrador cancela una cita confirmada que todavía no empieza (POST); el turno vuelve a quedar libre."""
    http_method_names = ['post']

    def post(self, request, pk):
        cita = get_object_or_404(Cita, pk=pk)
        try:
            AgendaService.cancelar(cita)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'Se canceló la cita de {cita.mascota}. El horario quedó libre.')
        destino = request.POST.get('volver', '')
        # Solo se vuelve a la propia gestión de citas (nunca a una URL de afuera)
        if not destino.startswith(reverse('citas:gestion_citas')):
            destino = reverse('citas:gestion_citas')
        return redirect(destino)


class GestionHorariosView(AdministradorRequeridoMixin, TemplateView):
    """La semana de toda la clínica: una fila por veterinario y una columna por día, con sus bloques."""
    template_name = 'citas/gestion/horarios.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(HorarioService.semana_de_la_clinica(semana_pedida(self.request.GET.get('semana'))))
        return contexto
