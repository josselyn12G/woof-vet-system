"""Datos que necesitan todas las páginas del panel: cuántos avisos sin leer tiene la persona (la campana)."""
from .services import NotificacionService


def notificaciones(request):
    """El número de la campana del panel (0 sin sesión, sin consultar la base)."""
    if not request.user.is_authenticated:
        return {'notificaciones_sin_leer': 0}
    return {'notificaciones_sin_leer': NotificacionService.no_leidas(request.user)}
