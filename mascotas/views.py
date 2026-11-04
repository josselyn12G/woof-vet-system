from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from cuentas.mixins import AdministradorRequeridoMixin, SuperadminRequeridoMixin
from cuentas.models import Roles

from .forms import EspecieForm, MascotaForm, MascotaGestionForm, RazaForm
from .models import Especie, Mascota, Raza
from .services import CatalogoService, MascotaService, foto_visible


class MascotasDelUsuarioMixin(LoginRequiredMixin):
    """Sin sesión redirige al login (?next=...). Con sesión, solo deja ver las mascotas propias:
    la de otro cliente no está en la consulta, así que get_object() responde 404.
    "Mis mascotas" es del cliente: otro rol que llega aquí (un enlace viejo, un ?next=) vuelve a su panel."""
    model = Mascota
    roles_permitidos = (Roles.CLIENTE,)   # también lo revisa el login antes de seguir un ?next=

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.rol not in self.roles_permitidos:
            return redirect('cuentas:panel')
        return super().dispatch(request, *args, **kwargs)

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

    def get_context_data(self, **kwargs):
        # La flecha y "Cancelar": a la ficha al editar, a la lista al registrar
        kwargs['volver'] = (reverse('mascotas:detalle', kwargs={'pk': self.object.pk}) if self.object
                            else reverse('mascotas:lista'))
        return super().get_context_data(**kwargs)


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
        resumen = MascotaService.resumen_de_la_clinica()
        contexto.update({
            'buscar': self.buscar(),
            # Solo se marca un filtro que existe (una especie inventada en la URL queda en "Todas")
            'especie_elegida': especie if any(fila['codigo'] == especie for fila in resumen['por_especie']) else '',
            'resumen': resumen,
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


# ---------------------------------------------------------------------------
# Superadministrador: crea, corrige y elimina la ficha de cualquier mascota (también cambia su dueño)
# ---------------------------------------------------------------------------
class MascotaGestionadaMixin(SuperadminRequeridoMixin):
    """Solo el superadministrador (403 para los demás). La foto se ve con tiene_foto, sin traer los bytes."""
    model = Mascota

    def get_queryset(self):
        return Mascota.objects.select_related('dueno').con_foto()


class FormularioGestionMixin(MascotaGestionadaMixin, SuccessMessageMixin):
    form_class = MascotaGestionForm
    template_name = 'mascotas/gestion/formulario.html'

    def get_context_data(self, **kwargs):
        kwargs['volver'] = (reverse('mascotas:gestion_detalle', kwargs={'pk': self.object.pk}) if self.object
                            else reverse('mascotas:gestion'))
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return reverse('mascotas:gestion_detalle', kwargs={'pk': self.object.pk})


class MascotaGestionCreateView(FormularioGestionMixin, CreateView):
    success_message = 'Se registró a %(nombre)s.'

    def get_initial(self):
        # ?dueno=<id> deja elegido al dueño (por ejemplo, desde la búsqueda de un cliente)
        return {'dueno': self.request.GET.get('dueno')}


class MascotaGestionUpdateView(FormularioGestionMixin, UpdateView):
    context_object_name = 'mascota'
    success_message = 'Se guardaron los cambios de %(nombre)s.'

    def get_context_data(self, **kwargs):
        # Si el POST tiene errores, self.object ya trae lo que se escribió: el título usa el nombre guardado
        kwargs['nombre_original'] = MascotaService.nombre_guardado(self.object.pk)
        return super().get_context_data(**kwargs)


class MascotaGestionDeleteView(MascotaGestionadaMixin, DeleteView):
    """GET muestra la confirmación (con cuántas citas se borran con ella); solo el POST borra."""
    template_name = 'mascotas/gestion/confirmar_eliminar.html'
    context_object_name = 'mascota'
    success_url = reverse_lazy('mascotas:gestion')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['total_citas'] = self.object.citas.count()
        return contexto

    def form_valid(self, form):
        messages.success(self.request, f'Se eliminó la ficha de {self.object.nombre}.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Superadministrador: el catálogo de especies y razas que se ofrece al registrar una mascota
# ---------------------------------------------------------------------------
class EspecieListView(SuperadminRequeridoMixin, TemplateView):
    """Cada especie con sus razas, cuántas mascotas tiene y sus acciones."""
    template_name = 'mascotas/gestion/especies.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['especies'] = CatalogoService.especies_con_razas()
        return contexto


class CatalogoFormularioMixin(SuperadminRequeridoMixin, SuccessMessageMixin):
    template_name = 'mascotas/gestion/catalogo_formulario.html'
    success_url = reverse_lazy('mascotas:especies')


class EspecieCreateView(CatalogoFormularioMixin, CreateView):
    form_class = EspecieForm
    success_message = 'Se agregó la especie %(nombre)s.'


class EspecieUpdateView(CatalogoFormularioMixin, UpdateView):
    model = Especie
    form_class = EspecieForm
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class RazaCreateView(CatalogoFormularioMixin, CreateView):
    form_class = RazaForm
    success_message = 'Se agregó la raza %(nombre)s.'

    def get_initial(self):
        # ?especie=<id> desde el "Agregar raza" de una especie
        return {'especie': self.request.GET.get('especie')}


class RazaUpdateView(CatalogoFormularioMixin, UpdateView):
    model = Raza
    form_class = RazaForm
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class CatalogoEliminarView(SuperadminRequeridoMixin, View):
    """Borra una especie o una raza (POST). Si alguna mascota la usa no se borra: se ofrece desactivarla."""
    http_method_names = ['post']
    modelo = None

    def post(self, request, pk):
        elemento = get_object_or_404(self.modelo, pk=pk)
        if CatalogoService.eliminar(elemento):
            messages.success(request, f'Se eliminó {elemento}.')
        else:
            messages.error(request, f'{elemento} tiene mascotas registradas y no se puede eliminar. Desactívala en su lugar.')
        return redirect('mascotas:especies')


class EspecieEliminarView(CatalogoEliminarView):
    modelo = Especie


class RazaEliminarView(CatalogoEliminarView):
    modelo = Raza
