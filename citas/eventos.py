"""
Los eventos de las citas (patrón Observer con señales propias de Django).

Cuando una cita se agenda, se reprograma o se cancela, citas lo anuncia y no sabe quién escucha. La app
notificaciones se suscribe (notificaciones/receptores.py) y avisa al cliente y al veterinario. Así citas no
depende de notificaciones: se puede agregar otro oyente (por ejemplo, un SMS) sin tocar el Core.

Se anuncian con anunciar_al_confirmar(): solo cuando la transacción termina bien, para que nadie reciba un
aviso de un cambio que se deshizo.
"""
from django.db import transaction
from django.dispatch import Signal

# Cada señal se envía con sender=Cita y estos argumentos:
cita_agendada = Signal()       # cita
cita_reprogramada = Signal()   # cita, inicio_anterior
cita_cancelada = Signal()      # cita, cancelada_por, motivo


def anunciar_al_confirmar(evento, cita, **datos):
    """Envía el evento cuando la transacción se confirma (fuera de una transacción, enseguida)."""
    transaction.on_commit(lambda: evento.send(sender=type(cita), cita=cita, **datos))
