"""«Mis mascotas» del cliente: listar, ver, el carnet, registrar, editar, eliminar y la foto."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from ..forms import MascotaForm
from ..mixins import FormularioMascotaMixin, MascotasDelUsuarioMixin
from ..services import MascotaService, foto_visible


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
