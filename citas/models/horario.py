"""Los bloques de disponibilidad del veterinario (Mi horario)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from cuentas.models import Roles


class HorarioVeterinario(models.Model):
    """
    Representa un bloque de disponibilidad de un veterinario en una fecha.

    Permite registrar las horas de inicio y fin de cada bloque, evitando
    horarios inválidos y cruces con otros bloques del mismo veterinario.
    """
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='horarios',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField('hora de inicio')
    hora_fin = models.TimeField('hora de fin')

    class Meta:
        verbose_name = 'horario del veterinario'
        verbose_name_plural = 'horarios de los veterinarios'
        ordering = ['fecha', 'hora_inicio']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hora_fin__gt=models.F('hora_inicio')),
                name='horario_fin_despues_del_inicio',
            ),
        ]

    def __str__(self):
        return f'{self.veterinario} · {self.fecha:%d/%m/%Y} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}'

    def clean(self):
        """
        Valida el bloque antes de guardarlo (lo llaman full_clean() y los formularios).

        Comprueba que la hora de fin sea posterior a la de inicio y que el bloque
        no se superponga con otro del mismo veterinario ese día.
        """
        # Si falta un dato, el error de ese campo ya lo muestra el formulario
        if not (self.veterinario_id and self.fecha and self.hora_inicio and self.hora_fin):
            return

        if self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la hora de inicio.'})

        # Dos bloques se cruzan si uno empieza antes de que el otro termine (RF-07, RF-08).
        # Los bloques seguidos (9:00-10:00 y 10:00-11:00) no se cruzan
        cruzado = (
            HorarioVeterinario.objects
            .filter(veterinario_id=self.veterinario_id, fecha=self.fecha,
                    hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio)
            .exclude(pk=self.pk)
            .first()
        )
        if cruzado:
            raise ValidationError(
                f'Se cruza con otro bloque de ese día ({cruzado.hora_inicio:%H:%M} a {cruzado.hora_fin:%H:%M}).'
            )
