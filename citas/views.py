from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, Count, ExpressionWrapper, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin, ClienteRequeridoMixin, VeterinarioRequeridoMixin
from cuentas.models import Roles
from mascotas.models import Mascota

from .forms import AgendarCitaForm, HorarioForm, MisServiciosForm, ServicioForm
from .models import Cita, EstadoCita, HorarioVeterinario, Servicio
from .services import AgendaService

# Filtro de estado del catálogo: valor en la URL -> condición
ESTADOS_SERVICIO = {'activos': True, 'inactivos': False}


class ServicioListView(AdministradorRequeridoMixin, ListView):
    """Catálogo de servicios de la clínica (HU-25, RF-04): buscador y filtro por estado."""
    template_name = 'citas/servicios/lista.html'
    context_object_name = 'servicios'
    paginate_by = 20

    def get_queryset(self):
        servicios = Servicio.objects.prefetch_related('veterinarios')
        buscar = self.request.GET.get('q', '').strip()
        if buscar:
            servicios = servicios.filter(Q(nombre__icontains=buscar) | Q(descripcion__icontains=buscar))
        estado = self.request.GET.get('estado', '')
        if estado in ESTADOS_SERVICIO:  # un estado inventado en la URL se ignora
            servicios = servicios.filter(activo=ESTADOS_SERVICIO[estado])
        return servicios

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
        servicio.activo = not servicio.activo
        servicio.save(update_fields=['activo'])
        if servicio.activo:
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
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                f'{self.object.nombre} tiene citas registradas y no se puede eliminar. Desactívalo en su lugar.',
            )
            return redirect('citas:servicios')
        messages.success(self.request, f'{self.object.nombre} se eliminó.')
        return redirect(self.success_url)


# ---------- Mi horario (veterinario): HU-26, RF-07 a RF-10 ----------

def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def semana_pedida(texto):
    """El lunes de la semana que llega por ?semana=2026-11-04 (cualquier día sirve). Sin fecha o con
    una fecha inventada, la semana actual."""
    try:
        return lunes_de(date.fromisoformat(texto or ''))
    except ValueError:
        return lunes_de(timezone.localdate())


def url_semana(fecha):
    return f"{reverse('citas:horario')}?semana={lunes_de(fecha).isoformat()}"


def minutos(bloque):
    inicio = datetime.combine(bloque.fecha, bloque.hora_inicio)
    return (datetime.combine(bloque.fecha, bloque.hora_fin) - inicio).seconds // 60


class HorarioDelVeterinarioMixin(VeterinarioRequeridoMixin):
    """Solo el veterinario entra (403 para los demás) y solo ve sus bloques: el de otro veterinario
    no está en la consulta, así que get_object() responde 404."""
    model = HorarioVeterinario

    def get_queryset(self):
        return HorarioVeterinario.objects.filter(veterinario=self.request.user)


class MiHorarioView(HorarioDelVeterinarioMixin, SuccessMessageMixin, CreateView):
    """La semana con sus bloques, el formulario "Nuevo bloque" y los servicios que atiende."""
    form_class = HorarioForm
    template_name = 'citas/horario/semana.html'
    success_message = 'Se agregó el bloque del %(fecha)s de %(hora_inicio)s a %(hora_fin)s.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # El veterinario siempre es quien inició sesión; va antes de validar para revisar los cruces
        kwargs['instance'] = HorarioVeterinario(veterinario=self.request.user)
        return kwargs

    def get_initial(self):
        # Fecha sugerida: hoy si se mira la semana actual; si no, el lunes de la semana elegida
        hoy = timezone.localdate()
        lunes = semana_pedida(self.request.GET.get('semana'))
        return {'fecha': max(lunes, hoy) if lunes + timedelta(days=6) >= hoy else lunes}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        lunes = semana_pedida(self.request.GET.get('semana'))
        domingo = lunes + timedelta(days=6)
        bloques = list(self.get_queryset().filter(fecha__range=(lunes, domingo)))

        contexto['dias'] = [
            {
                'fecha': dia,
                'bloques': [bloque for bloque in bloques if bloque.fecha == dia],
                'es_hoy': dia == hoy,
                'ya_paso': dia < hoy,
            }
            for dia in (lunes + timedelta(days=i) for i in range(7))
        ]
        horas, resto = divmod(sum(minutos(bloque) for bloque in bloques), 60)
        contexto['total_semana'] = f'{horas} h' + (f' {resto} min' if resto else '')
        contexto['lunes'], contexto['domingo'] = lunes, domingo
        contexto['semana_anterior'] = lunes - timedelta(days=7)
        contexto['semana_siguiente'] = lunes + timedelta(days=7)
        contexto['es_semana_actual'] = lunes == lunes_de(hoy)
        contexto['se_puede_copiar'] = domingo >= hoy  # no tiene sentido copiar a una semana que ya pasó

        contexto['servicios_form'] = MisServiciosForm(
            initial={'servicios': self.request.user.servicios.filter(activo=True)},
        )
        return contexto

    def get_success_message(self, cleaned_data):
        return self.success_message % {
            'fecha': cleaned_data['fecha'].strftime('%d/%m'),
            'hora_inicio': cleaned_data['hora_inicio'].strftime('%H:%M'),
            'hora_fin': cleaned_data['hora_fin'].strftime('%H:%M'),
        }

    def get_success_url(self):
        return url_semana(self.object.fecha)


class HorarioEditarView(HorarioDelVeterinarioMixin, SuccessMessageMixin, UpdateView):
    form_class = HorarioForm
    template_name = 'citas/horario/editar.html'
    context_object_name = 'bloque'
    success_message = 'Se guardaron los cambios del bloque.'

    def get_success_url(self):
        return url_semana(self.object.fecha)


class HorarioEliminarView(HorarioDelVeterinarioMixin, DeleteView):
    """Solo POST (el botón pide confirmación en el navegador). Cuando exista Cita, aquí se debe impedir
    quitar un bloque que ya tiene citas reservadas (HU-26)."""
    http_method_names = ['post']

    def form_valid(self, form):
        fecha = self.object.fecha
        self.object.delete()
        messages.success(self.request, 'Se quitó el bloque de tu horario.')
        return redirect(url_semana(fecha))


class CopiarSemanaView(VeterinarioRequeridoMixin, View):
    """Copia los bloques de la semana anterior en la semana elegida (HU-26). Se saltan los días que ya
    pasaron y los bloques que se cruzarían con otros que ya están cargados."""
    http_method_names = ['post']

    def post(self, request):
        lunes = semana_pedida(request.POST.get('semana'))
        hoy = timezone.localdate()
        propios = HorarioVeterinario.objects.filter(veterinario=request.user)
        anteriores = propios.filter(fecha__range=(lunes - timedelta(days=7), lunes - timedelta(days=1)))
        if not anteriores:
            messages.error(request, 'La semana anterior no tiene bloques para copiar.')
            return redirect(url_semana(lunes))

        copiados = omitidos = 0
        for bloque in anteriores:
            nuevo = HorarioVeterinario(veterinario=request.user, fecha=bloque.fecha + timedelta(days=7),
                                       hora_inicio=bloque.hora_inicio, hora_fin=bloque.hora_fin)
            cruza = propios.filter(fecha=nuevo.fecha, hora_inicio__lt=nuevo.hora_fin,
                                   hora_fin__gt=nuevo.hora_inicio).exists()
            if nuevo.fecha < hoy or cruza:
                omitidos += 1
                continue
            nuevo.save()
            copiados += 1

        if copiados:
            texto = f'Se copiaron {copiados} bloque{"s" if copiados != 1 else ""} de la semana anterior.'
            if omitidos:
                texto += f' {omitidos} no se copiaron porque el día ya pasó o se cruzaban con tu horario.'
            messages.success(request, texto)
        else:
            messages.error(request, 'No se copió ningún bloque: los días ya pasaron o se cruzaban con tu horario.')
        return redirect(url_semana(lunes))


class MisServiciosView(VeterinarioRequeridoMixin, View):
    """Guarda los servicios que atiende el veterinario: solo aparece al agendar los que marque."""
    http_method_names = ['post']

    def post(self, request):
        formulario = MisServiciosForm(request.POST)
        destino = url_semana(semana_pedida(request.POST.get('semana')))
        if not formulario.is_valid():
            messages.error(request, 'Elige servicios de la lista.')
            return redirect(destino)
        # Los servicios desactivados no se muestran en las casillas, así que se conservan como estaban
        inactivos = list(request.user.servicios.filter(activo=False))
        request.user.servicios.set(list(formulario.cleaned_data['servicios']) + inactivos)
        cantidad = len(formulario.cleaned_data['servicios'])
        messages.success(request, f'Ahora atiendes {cantidad} servicio{"s" if cantidad != 1 else ""}.')
        return redirect(destino)


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


def leer_fecha(texto):
    """"2026-11-03" -> date; None si viene vacía o inventada."""
    try:
        return date.fromisoformat(texto or '')
    except ValueError:
        return None


class TurnosDelDiaView(ClienteRequeridoMixin, View):
    """
    Devuelve en JSON las horas libres de un servicio en una fecha, agrupadas por veterinario.
    La pide agendar.js al tocar un día; la regla es la misma que usa agendar().
    """

    def get(self, request):
        servicio = Servicio.objects.filter(pk=request.GET.get('servicio') or 0, activo=True).first()
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
        servicio = Servicio.objects.filter(pk=request.GET.get('servicio') or 0, activo=True).first()
        try:
            anio, mes = (int(parte) for parte in request.GET.get('mes', '').split('-'))
            date(anio, mes, 1)
        except ValueError:
            anio = None

        if not (servicio and anio):
            return JsonResponse({'dias': []})
        dias = AgendaService.dias_del_servicio(servicio, anio, mes)
        return JsonResponse({'dias': [dia.isoformat() for dia in dias]})


# Pestañas de Mis citas: valor en la URL (?vista=) -> nombre que se muestra
VISTAS_CITAS = {'proximas': 'Próximas', 'pasadas': 'Pasadas', 'canceladas': 'Canceladas'}


class MisCitasView(ClienteRequeridoMixin, TemplateView):
    """
    Las citas de las mascotas del cliente en tres pestañas (?vista=proximas|pasadas|canceladas),
    agrupadas por día; al costado, su próxima cita, la última y sus mascotas.
    """
    template_name = 'citas/mis_citas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        ahora = timezone.now()
        # Cada cliente ve solo las citas de sus mascotas; tiene_foto dice si mostrar la foto de la mascota
        citas = list(
            Cita.objects.filter(mascota__dueno=self.request.user)
            .select_related('mascota', 'servicio', 'veterinario')
            .defer('mascota__foto')
            .annotate(foto_mascota=ExpressionWrapper(Q(mascota__foto__isnull=False), output_field=BooleanField()))
        )
        for cita in citas:
            cita.mascota.tiene_foto = cita.foto_mascota

        proximas = [c for c in citas if c.estado == EstadoCita.CONFIRMADA and c.inicio > ahora]
        canceladas = sorted((c for c in citas if c.estado == EstadoCita.CANCELADA), key=lambda c: c.inicio, reverse=True)
        pasadas = sorted((c for c in citas if c not in proximas and c not in canceladas), key=lambda c: c.inicio, reverse=True)
        listas = {'proximas': proximas, 'pasadas': pasadas, 'canceladas': canceladas}

        vista = self.request.GET.get('vista', 'proximas')
        if vista not in VISTAS_CITAS:   # una pestaña inventada en la URL vuelve a Próximas
            vista = 'proximas'

        # Las citas de la pestaña, agrupadas por día (fecha local): [(fecha, [citas]), ...]
        por_dia = {}
        for cita in listas[vista]:
            por_dia.setdefault(timezone.localtime(cita.inicio).date(), []).append(cita)

        mascotas = (
            Mascota.objects.filter(dueno=self.request.user).defer('foto')
            .annotate(tiene_foto=ExpressionWrapper(Q(foto__isnull=False), output_field=BooleanField()))
            .order_by('nombre')
        )
        contexto.update({
            # La reserva del pop-up "Agendar cita" (el mismo formulario de AgendarCitaView)
            'form': AgendarCitaForm(cliente=self.request.user),
            'abrir_agendar': 'agendar' in self.request.GET,   # ?agendar abre el pop-up al cargar (desde el inicio)
            'vista': vista,
            'pestanas': [(valor, nombre, len(listas[valor])) for valor, nombre in VISTAS_CITAS.items()],
            'por_dia': list(por_dia.items()),
            'proximas': proximas,
            'proxima': proximas[0] if proximas else None,
            'ultima': pasadas[0] if pasadas else None,
            'mascotas': mascotas,
            'hoy': timezone.localdate(),
            'ahora': ahora,
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
        try:
            fecha = date.fromisoformat(self.request.GET.get('fecha', ''))
        except ValueError:
            fecha = timezone.localdate()   # una fecha inventada vuelve a hoy

        citas = (
            Cita.objects.filter(veterinario=self.request.user, inicio__date=fecha)
            .select_related('mascota', 'mascota__dueno', 'servicio')
            .defer('mascota__foto')
        )
        contexto.update({
            'fecha': fecha,
            'hoy': timezone.localdate(),
            'anterior': fecha - timedelta(days=1),
            'siguiente': fecha + timedelta(days=1),
            'citas': citas,
            'activas': sum(1 for cita in citas if cita.estado != EstadoCita.CANCELADA),
            'bloques': HorarioVeterinario.objects.filter(veterinario=self.request.user, fecha=fecha),
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
        mascotas = (
            Mascota.objects.filter(dueno__rol=Roles.CLIENTE)
            .select_related('dueno')
            .defer('foto')   # tiene_foto basta para mostrar su foto, sin traer los bytes
            .annotate(
                tiene_foto=ExpressionWrapper(Q(foto__isnull=False), output_field=BooleanField()),
                citas_conmigo=Count('citas', filter=Q(citas__veterinario=self.request.user)),
            )
            .order_by('nombre')
        )
        buscar = self.request.GET.get('q', '').strip()
        if buscar:
            mascotas = mascotas.filter(
                Q(nombre__icontains=buscar)
                | Q(dueno__first_name__icontains=buscar) | Q(dueno__last_name__icontains=buscar)
                | Q(dueno__username__icontains=buscar) | Q(dueno__email__icontains=buscar)
                | Q(dueno__cedula__icontains=buscar) | Q(dueno__telefono__icontains=buscar)
            )
        if self.request.GET.get('mios'):
            mascotas = mascotas.filter(citas_conmigo__gt=0)
        return mascotas

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.request.GET.get('q', '').strip()
        contexto['solo_mios'] = bool(self.request.GET.get('mios'))
        return contexto
