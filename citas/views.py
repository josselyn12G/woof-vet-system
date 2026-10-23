from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin

from .forms import ServicioForm
from .models import Servicio

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
