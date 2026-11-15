"""La calificación que el cliente le da a una cita atendida (F7, RF-21)."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .cita import Cita

ESTRELLAS_MIN, ESTRELLAS_MAX = 1, 5


class Calificacion(models.Model):
    """
    La opinión del cliente sobre una cita atendida: de 1 a 5 estrellas y un comentario opcional.

    Una sola por cita (OneToOne): calificar dos veces la misma cita lo rechaza la base de datos.
    """
    cita = models.OneToOneField(Cita, on_delete=models.CASCADE, related_name='calificacion')
    estrellas = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(ESTRELLAS_MIN, 'Elige al menos 1 estrella.'),
            MaxValueValidator(ESTRELLAS_MAX, 'Son 5 estrellas como máximo.'),
        ],
    )
    comentario = models.TextField(max_length=500, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'calificación'
        verbose_name_plural = 'calificaciones'
        ordering = ['-creado']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estrellas__gte=ESTRELLAS_MIN, estrellas__lte=ESTRELLAS_MAX),
                name='calificacion_estrellas_de_1_a_5',
            ),
        ]

    def __str__(self):
        return f'{self.estrellas} ★ · {self.cita}'
