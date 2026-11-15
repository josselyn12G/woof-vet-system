from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .forms.perfil import PerfilVeterinarioForm
from .models import ROLES_DE_GESTION, Roles
from .services.perfiles import PerfilVeterinarioService
from .services.usuarios import PoliticaDeCuentas, UsuarioService

# ---------------------------------------------------------------------------
# Acceso por rol
# ---------------------------------------------------------------------------


class RolRequeridoMixin(LoginRequiredMixin):
    """Exige sesión iniciada y que el rol del usuario esté en roles_permitidos (si no, 403)."""
    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.rol not in self.roles_permitidos:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ClienteRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = (Roles.CLIENTE,)


class VeterinarioRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = (Roles.VETERINARIO,)


class AdministradorRequeridoMixin(RolRequeridoMixin):
    """Pantallas de la clínica: las abre el administrador y también el superadministrador."""
    roles_permitidos = ROLES_DE_GESTION


class SuperadminRequeridoMixin(RolRequeridoMixin):
    """Gestión del personal (administradores y veterinarios): solo el superadministrador."""
    roles_permitidos = (Roles.SUPERADMIN,)


# ---------------------------------------------------------------------------
# Comportamiento que comparten varias vistas del panel
# ---------------------------------------------------------------------------
class BusquedaMixin:
    """El texto del buscador (?q=), sin espacios de más."""

    def buscar(self):
        return self.request.GET.get('q', '').strip()


class CuentaGestionableMixin:
    """La cuenta de la URL, solo si quien la abre puede gestionarla (si no, 403). El formulario recibe al actor."""
    context_object_name = 'persona'

    def get_queryset(self):
        return UsuarioService.todas()

    def get_object(self, queryset=None):
        persona = super().get_object(queryset)
        PoliticaDeCuentas.exigir_gestion(self.request.user, persona)
        return persona

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs


class PerfilVeterinarioEnFormularioMixin:
    """
    Si la cuenta que se edita es de un veterinario, la misma página trae su perfil (especialidad y
    verificación) y los dos formularios se guardan juntos. Se usa con un UpdateView de la cuenta.
    """

    def crear_perfil_form(self):
        if not self.object.es_veterinario:
            return None
        datos = self.request.POST if self.request.method == 'POST' else None
        return PerfilVeterinarioForm(datos, instance=PerfilVeterinarioService.de(self.object))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Antes de validar la cuenta: si en este envío se le cambia el rol, se decide con el que tenía
        self.perfil_form = self.crear_perfil_form()
        form = self.get_form()
        perfil_valido = self.perfil_form is None or self.perfil_form.is_valid()
        if form.is_valid() and perfil_valido:
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        if self.perfil_form is not None:
            self.perfil_form.save()
        return respuesta

    def get_context_data(self, **kwargs):
        if 'perfil_form' not in kwargs:
            kwargs['perfil_form'] = getattr(self, 'perfil_form', None) or self.crear_perfil_form()
        return super().get_context_data(**kwargs)
