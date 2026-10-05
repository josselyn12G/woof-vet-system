from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import BooleanField, ExpressionWrapper, Q
from django.http import Http404, HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import MascotaForm
from .models import Mascota


class MascotasDelUsuarioMixin(LoginRequiredMixin):
    """Sin sesión redirige al login (?next=...). Con sesión, solo deja ver las mascotas propias:
    la de otro cliente no está en la consulta, así que get_object() responde 404."""
    model = Mascota

    def get_queryset(self):
        # defer('foto'): no se traen los bytes de la foto; tiene_foto solo dice si hay una
        return (
            Mascota.objects.filter(dueno=self.request.user)
            .defer('foto')
            .annotate(tiene_foto=ExpressionWrapper(Q(foto__isnull=False), output_field=BooleanField()))
        )


class MascotaListView(MascotasDelUsuarioMixin, ListView):
    template_name = 'mascotas/lista.html'
    context_object_name = 'mascotas'


class MascotaDetailView(MascotasDelUsuarioMixin, DetailView):
    template_name = 'mascotas/detalle.html'
    context_object_name = 'mascota'


class MascotaCreateView(MascotasDelUsuarioMixin, SuccessMessageMixin, CreateView):
    form_class = MascotaForm
    template_name = 'mascotas/formulario.html'
    success_message = '%(nombre)s se registró correctamente.'

    def form_valid(self, form):
        form.instance.dueno = self.request.user  # el dueño siempre es quien inició sesión
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('mascotas:detalle', kwargs={'pk': self.object.pk})


class MascotaUpdateView(MascotasDelUsuarioMixin, SuccessMessageMixin, UpdateView):
    form_class = MascotaForm
    template_name = 'mascotas/formulario.html'
    context_object_name = 'mascota'
    success_message = 'Los datos de %(nombre)s se actualizaron.'

    def get_context_data(self, **kwargs):
        # Si el POST tiene errores, self.object ya trae lo que se escribió: el título usa el nombre guardado
        kwargs['nombre_original'] = Mascota.objects.values_list('nombre', flat=True).get(pk=self.object.pk)
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
    La ve el dueño; los administradores (is_staff) también, para revisarla desde /admin/."""

    def get(self, request, pk):
        mascotas = Mascota.objects.filter(pk=pk, foto__isnull=False)
        if not request.user.is_staff:
            mascotas = mascotas.filter(dueno=request.user)
        foto = mascotas.values_list('foto', flat=True).first()
        if foto is None:
            raise Http404('La mascota no tiene foto.')

        respuesta = HttpResponse(bytes(foto), content_type='image/webp')
        # La URL lleva ?v=<fecha de actualización>: si la foto cambia, cambia la URL, así que se puede guardar en caché
        respuesta['Cache-Control'] = 'private, max-age=31536000'
        return respuesta
