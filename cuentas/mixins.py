from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import ROLES_DE_GESTION, Roles
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
