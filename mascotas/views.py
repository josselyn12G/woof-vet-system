from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin

from .forms import MascotaForm
from .models import Especies, Mascota
from .services import MascotaService, foto_visible


class MascotasDelUsuarioMixin(LoginRequiredMixin):
    """Sin sesión redirige al login (?next=...). Con sesión, solo deja ver las mascotas propias:
    la de otro cliente no está en la consulta, así que get_object() responde 404."""
    model = Mascota

    def get_queryset(self):
        return MascotaService.del_dueno(self.request.user)


class MascotaListView(MascotasDelUsuarioMixin, ListView):
    template_name = 'mascotas/lista.html'
    context_object_name = 'mascotas'


class MascotaDetailView(MascotasDelUsuarioMixin, DetailView):
    template_name = 'mascotas/detalle.html'
    context_object_name = 'mascota'


class MascotaCarnetView(MascotasDelUsuarioMixin, DetailView):
    """Carnet de vacunación (HU-36). Las vacunas llegan con la app historial (HU-35);
    mientras tanto el carnet se muestra vacío."""
    template_name = 'mascotas/carnet.html'
    context_object_name = 'mascota'


class FormularioMascotaMixin:
    """El formulario recibe al dueño para no repetir nombres entre sus mascotas."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['dueno'] = self.request.user
        return kwargs


class MascotaCreateView(MascotasDelUsuarioMixin, FormularioMascotaMixin, SuccessMessageMixin, CreateView):
    form_class = MascotaForm
    template_name = 'mascotas/formulario.html'
    success_message = '%(nombre)s se registró correctamente.'

    def form_valid(self, form):
        form.instance.dueno = self.request.user  # el dueño siempre es quien inició sesión
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('mascotas:detalle', kwargs={'pk': self.object.pk})


class MascotaUpdateView(MascotasDelUsuarioMixin, FormularioMascotaMixin, SuccessMessageMixin, UpdateView):
    form_class = MascotaForm
    template_name = 'mascotas/formulario.html'
    context_object_name = 'mascota'
    success_message = 'Los datos de %(nombre)s se actualizaron.'

    def get_context_data(self, **kwargs):
        # Si el POST tiene errores, self.object ya trae lo que se escribió: el título usa el nombre guardado
        kwargs['nombre_original'] = MascotaService.nombre_guardado(self.object.pk)
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return reverse_lazy('mascotas:detalle', kwargs={'pk': self.object.pk})


class MascotaDeleteView(MascotasDelUsuarioMixin, DeleteView):
    """GET muestra la confirmación; solo el POST del botón "Sí, eliminar" borra."""
    template_name = 'mascotas/confirmar_eliminar.html'
    context_object_name = 'mascota'
    success_url = reverse_lazy('mascotas:lista')

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.nombre} se eliminó.')
        return super().form_valid(form)


class FotoMascotaView(LoginRequiredMixin, View):
    """Entrega la foto guardada en la base como una imagen normal (<img src="/mascotas/1/foto/">).
    Quién puede verla lo decide foto_visible()."""

    def get(self, request, pk):
        foto = foto_visible(pk, request.user)
        if foto is None:
            raise Http404('La mascota no tiene foto.')

        respuesta = HttpResponse(foto, content_type='image/webp')
        # La URL lleva ?v=<fecha de actualización>: si la foto cambia, cambia la URL, así que se puede guardar en caché
        respuesta['Cache-Control'] = 'private, max-age=31536000'
        return respuesta


# ---------------------------------------------------------------------------
# Gestión de la clínica (administrador y superadministrador): todas las mascotas
# ---------------------------------------------------------------------------
class MascotaGestionListView(AdministradorRequeridoMixin, ListView):
    """Todas las mascotas con su dueño: buscador (mascota, dueño, cédula o teléfono) y filtro por especie."""
    template_name = 'mascotas/gestion/lista.html'
    context_object_name = 'mascotas'
    paginate_by = 12

    def get_queryset(self):
        return MascotaService.de_la_clinica(self.buscar(), self.request.GET.get('especie', ''))

    def buscar(self):
        return self.request.GET.get('q', '').strip()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        especie = self.request.GET.get('especie', '')
        contexto.update({
            'buscar': self.buscar(),
            'especie_elegida': especie if especie in Especies.values else '',
            'resumen': MascotaService.resumen_de_la_clinica(),
        })
        return contexto


class MascotaGestionDetailView(AdministradorRequeridoMixin, DetailView):
    """La ficha de cualquier mascota, con su dueño y su historial de citas."""
    template_name = 'mascotas/gestion/detalle.html'
    context_object_name = 'mascota'

    def get_object(self, queryset=None):
        try:
            return MascotaService.ficha_de_la_clinica(self.kwargs['pk'])
        except Mascota.DoesNotExist:
            raise Http404('No existe esa mascota.')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['citas'] = MascotaService.citas_de(self.object)
        return contexto
