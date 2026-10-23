from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin, VeterinarioRequeridoMixin

from .forms import HorarioForm, MisServiciosForm, ServicioForm
from .models import HorarioVeterinario, Servicio

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
