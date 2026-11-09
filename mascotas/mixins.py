"""
Mixins de las vistas de mascotas. Los de acceso por rol están en cuentas/mixins.py.

- MascotasDelUsuarioMixin y FormularioMascotaMixin: «Mis mascotas» del cliente.
- MascotaGestionadaMixin y FormularioGestionMixin: la ficha de cualquier mascota (superadministrador).
- CatalogoFormularioMixin: los formularios de especies y razas (superadministrador).
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy

from cuentas.mixins import SuperadminRequeridoMixin
from cuentas.models import Roles

from .forms import MascotaGestionForm
from .models import Mascota
from .services import MascotaService


class MascotasDelUsuarioMixin(LoginRequiredMixin):
    """Sin sesión redirige al login (?next=...). Con sesión, solo deja ver las mascotas propias:
    la de otro cliente no está en la consulta, así que get_object() responde 404.
    "Mis mascotas" es del cliente: otro rol que llega aquí (un enlace viejo, un ?next=) vuelve a su panel."""
    model = Mascota
    roles_permitidos = (Roles.CLIENTE,)   # también lo revisa el login antes de seguir un ?next=

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.rol not in self.roles_permitidos:
            return redirect('panel:panel')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return MascotaService.del_dueno(self.request.user)


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


class MascotaGestionadaMixin(SuperadminRequeridoMixin):
    """Solo el superadministrador (403 para los demás). La foto se ve con tiene_foto, sin traer los bytes."""
    model = Mascota

    def get_queryset(self):
        return MascotaService.fichas()


class FormularioGestionMixin(MascotaGestionadaMixin, SuccessMessageMixin):
    form_class = MascotaGestionForm
    template_name = 'mascotas/gestion/formulario.html'

    def get_context_data(self, **kwargs):
        kwargs['volver'] = (reverse('mascotas:gestion_detalle', kwargs={'pk': self.object.pk}) if self.object
                            else reverse('mascotas:gestion'))
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return reverse('mascotas:gestion_detalle', kwargs={'pk': self.object.pk})


class CatalogoFormularioMixin(SuperadminRequeridoMixin, SuccessMessageMixin):
    template_name = 'mascotas/gestion/catalogo_formulario.html'
    success_url = reverse_lazy('mascotas:especies')
