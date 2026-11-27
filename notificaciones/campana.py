"""
La campana del panel: cuántos avisos sin leer tiene la persona, sus últimos avisos agrupados y marcarlos leídos.

Salió de NotificacionService (segregación de interfaces): la vista de la campana y el procesador de contexto
solo necesitan esto, no cómo se crean, se envían o se reintentan los avisos.
"""
from django.utils import timezone
from django.utils.formats import date_format

from .models import Notificacion


class CampanaService:
    """Lo que ve la persona en la campana del panel y en la página de avisos."""

    @staticmethod
    def no_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).count()

    @staticmethod
    def de(usuario, cantidad=50):
        return list(Notificacion.objects.filter(usuario=usuario).select_related('cita')[:cantidad])

    @staticmethod
    def hace(momento, ahora=None):
        """'Ahora', 'Hace 5 min', 'Hace 2 h', 'Ayer' o la fecha ('12 nov'): lo que muestra el panel de la campana."""
        ahora = ahora or timezone.now()
        segundos = (ahora - momento).total_seconds()
        if segundos < 60:
            return 'Ahora'
        if segundos < 3600:
            return f'Hace {int(segundos // 60)} min'
        dias = (timezone.localtime(ahora).date() - timezone.localtime(momento).date()).days
        if dias == 0:
            return f'Hace {int(segundos // 3600)} h'
        if dias == 1:
            return 'Ayer'
        return date_format(timezone.localtime(momento), 'j M')

    @staticmethod
    def agrupadas(usuario, cantidad=30, ahora=None):
        """
        El panel de la campana: los últimos avisos en tres grupos [(clave, título, [aviso, ...]), ...]:
        hoy, esta semana (los 6 días anteriores) y antes. Cada aviso trae su 'hace' corto.
        """
        ahora = ahora or timezone.now()
        hoy = timezone.localtime(ahora).date()
        grupos = {'hoy': [], 'semana': [], 'antes': []}
        for aviso in CampanaService.de(usuario, cantidad):
            aviso.hace = CampanaService.hace(aviso.creado, ahora)
            dias = (hoy - timezone.localtime(aviso.creado).date()).days
            grupos['hoy' if dias == 0 else 'semana' if dias < 7 else 'antes'].append(aviso)
        return [('hoy', 'Hoy', grupos['hoy']), ('semana', 'Esta semana', grupos['semana']),
                ('antes', 'Antes', grupos['antes'])]

    @staticmethod
    def marcar_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
