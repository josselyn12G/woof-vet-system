"""La cita: la reserva de un servicio para una mascota con un veterinario, y sus estados."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from cuentas.models import Roles

from .servicio import Servicio


class EstadoCita(models.TextChoices):
    """
    Estados por los que pasa una cita.

    Nace confirmada y termina atendida, no asistió o cancelada.
    Solo una cita cancelada libera su horario para otro cliente.
    """
    CONFIRMADA = 'confirmada', 'Confirmada'
    ATENDIDA = 'atendida', 'Atendida'
    NO_ASISTIO = 'no_asistio', 'No asistió'
    CANCELADA = 'cancelada', 'Cancelada'


class Cita(models.Model):
    """
    Representa la reserva de un servicio para una mascota con un veterinario.

    Guarda el inicio y el fin del turno y una copia del precio al agendar.
    Nace confirmada; dos citas activas del mismo veterinario no pueden cruzarse.
    """
    mascota = models.ForeignKey('mascotas.Mascota', on_delete=models.CASCADE, related_name='citas')
    # PROTECT: un veterinario o un servicio con citas no se borra, así no se pierde la agenda
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='citas_atendidas',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name='citas')
    inicio = models.DateTimeField()
    # fin = inicio + duración del servicio; lo calcula AgendaService, no el usuario
    fin = models.DateTimeField()
    # Copia del precio al agendar: si el servicio cambia de precio, la cita conserva el acordado
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    motivo = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=12, choices=EstadoCita.choices, default=EstadoCita.CONFIRMADA)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'cita'
        verbose_name_plural = 'citas'
        ordering = ['inicio']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fin__gt=models.F('inicio')),
                name='cita_fin_despues_del_inicio',
            ),
            # Red de seguridad en la base: dos citas activas del mismo veterinario no empiezan a la misma hora.
            # Las canceladas no cuentan (~ es NO), así su turno vuelve a quedar libre
            models.UniqueConstraint(
                fields=['veterinario', 'inicio'],
                condition=~models.Q(estado=EstadoCita.CANCELADA),
                name='cita_unica_por_veterinario_y_hora',
            ),
        ]

    def __str__(self):
        inicio = timezone.localtime(self.inicio)
        return f'{self.mascota} · {inicio:%d/%m/%Y %H:%M}'
