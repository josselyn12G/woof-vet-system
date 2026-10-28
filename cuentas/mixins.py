from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Roles


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
    roles_permitidos = (Roles.ADMINISTRADOR,)
