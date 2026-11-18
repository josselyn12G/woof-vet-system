"""Los avisos de las citas (F8, RF-23 y RF-24): se guardan para la campana del panel y se envían por correo."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import render_to_string

from cuentas.services.correo import adjuntar_logo

from .cita import Cita

registro = logging.getLogger(__name__)


class TipoNotificacion(models.TextChoices):
    AGENDADA = 'agendada', 'Cita agendada'
    REPROGRAMADA = 'reprogramada', 'Cita reprogramada'
    CANCELADA = 'cancelada', 'Cita cancelada'
    RECORDATORIO = 'recordatorio', 'Recordatorio de cita'


class Notificacion(models.Model):
    """
    Un aviso para un usuario (el cliente o el veterinario), casi siempre sobre una cita.

    enviar() lo manda por correo; leida dice si ya lo vio en la campana del panel.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones')
    tipo = models.CharField(max_length=15, choices=TipoNotificacion.choices)
    mensaje = models.TextField()
    creado = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'notificación'
        verbose_name_plural = 'notificaciones'
        ordering = ['-creado']
        indexes = [models.Index(fields=['usuario', 'leida'], name='notificacion_usuario_leida')]
        constraints = [
            # Red de seguridad del comando enviar_recordatorios: un solo recordatorio por cita y persona
            models.UniqueConstraint(
                fields=['cita', 'usuario'],
                condition=models.Q(tipo='recordatorio'),
                name='notificacion_un_recordatorio_por_cita',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} para {self.usuario}'

    def enviar(self):
        """
        Manda el aviso al correo del usuario. Devuelve True si salió.

        Si el correo falla (SMTP caído, dirección mala) no se rompe la cita: el aviso sigue guardado
        en la campana y el error queda en el registro del servidor. Con CORREO_AVISOS=False (Render)
        no se intenta enviar.
        """
        if not getattr(settings, 'CORREO_AVISOS', True):
            return False
        contexto = {'nombre': self.usuario.first_name or self.usuario.username, 'notificacion': self}
        correo = EmailMultiAlternatives(
            f'Woof · {self.get_tipo_display()}',
            render_to_string('citas/correos/notificacion.txt', contexto),
            None,
            [self.usuario.email],
        )
        correo.attach_alternative(render_to_string('citas/correos/notificacion.html', contexto), 'text/html')
        adjuntar_logo(correo)
        try:
            correo.send()
        except Exception:   # cualquier fallo del envío: se registra y la reserva sigue su curso
            registro.exception('No se pudo enviar la notificación %s a %s', self.pk, self.usuario.email)
            return False
        return True
