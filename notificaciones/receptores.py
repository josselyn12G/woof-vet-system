"""
Los oyentes de los eventos de las citas (patrón Observer): cada evento se convierte en los avisos del cliente
y del veterinario. Se conectan en NotificacionesConfig.ready().
"""
from django.dispatch import receiver

from citas.eventos import cita_agendada, cita_cancelada, cita_reprogramada

from .services import NotificacionService


@receiver(cita_agendada)
def avisar_cita_agendada(sender, cita, **kwargs):
    NotificacionService.cita_agendada(cita)


@receiver(cita_reprogramada)
def avisar_cita_reprogramada(sender, cita, inicio_anterior, **kwargs):
    NotificacionService.cita_reprogramada(cita, inicio_anterior)


@receiver(cita_cancelada)
def avisar_cita_cancelada(sender, cita, cancelada_por, motivo='', **kwargs):
    NotificacionService.cita_cancelada(cita, cancelada_por, motivo)
