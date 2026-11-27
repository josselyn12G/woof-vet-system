"""Los avisos de las citas (F8, RF-23 y RF-24) y de las vacunas (HU-37): se guardan para la campana del panel y se envían por correo."""
from django.conf import settings
from django.db import models

from .cita import Cita


class TipoNotificacion(models.TextChoices):
    AGENDADA = 'agendada', 'Cita agendada'
    REPROGRAMADA = 'reprogramada', 'Cita reprogramada'
    CANCELADA = 'cancelada', 'Cita cancelada'
    RECORDATORIO = 'recordatorio', 'Recordatorio de cita'
    VACUNA = 'vacuna', 'Recordatorio de vacuna'


class Notificacion(models.Model):
    """
    Un aviso para un usuario (el cliente o el veterinario), casi siempre sobre una cita. El recordatorio
    de vacuna no tiene cita: apunta a la dosis aplicada cuya próxima dosis se acerca.

    Solo guarda el aviso; mandarlo por correo es tarea de NotificacionService.enviar().
    leida dice si ya lo vio en la campana del panel.

    correo_enviado e intentos_correo son el registro del fallback: si el correo no sale, el aviso igual queda
    en la campana (el plan B) y el comando enviar_recordatorios lo vuelve a intentar más tarde, pocas veces.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones')
    vacuna_aplicada = models.ForeignKey(
        'historial.VacunaAplicada', on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones',
    )
    tipo = models.CharField(max_length=15, choices=TipoNotificacion.choices)
    mensaje = models.TextField()
    creado = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    correo_enviado = models.BooleanField(default=False)
    intentos_correo = models.PositiveSmallIntegerField(default=0)

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
            # Lo mismo para las vacunas: un solo recordatorio por dosis y persona
            models.UniqueConstraint(
                fields=['vacuna_aplicada', 'usuario'],
                condition=models.Q(tipo='vacuna'),
                name='notificacion_un_recordatorio_por_vacuna',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} para {self.usuario}'
