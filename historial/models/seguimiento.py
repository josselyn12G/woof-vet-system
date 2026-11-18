"""El seguimiento del tratamiento: el dueño marca cada día que le dio la dosis que indicó el veterinario."""
from django.db import models

from .consulta import Prescripcion


class TomaDia(models.Model):
    """
    Un día del tratamiento marcado como cumplido (versión simple de la tabla TOMA del ER: un check por día,
    no por toma). La dosis no se cambia aquí: es la de la receta. Solo se puede marcar un día una vez.
    """
    prescripcion = models.ForeignKey(Prescripcion, on_delete=models.CASCADE, related_name='dias_marcados')
    dia = models.DateField()
    marcada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'día del tratamiento'
        verbose_name_plural = 'días del tratamiento'
        ordering = ['dia']
        constraints = [
            models.UniqueConstraint(fields=['prescripcion', 'dia'], name='toma_un_check_por_dia'),
        ]

    def __str__(self):
        return f'{self.prescripcion.medicamento} · {self.dia:%d/%m/%Y}'
