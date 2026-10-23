from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from cuentas.models import Roles


class Servicio(models.Model):
    """Lo que ofrece la clínica (consulta general, vacunación...) con su duración y precio (HU-25)."""
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField('descripción', blank=True)
    duracion_min = models.PositiveIntegerField(
        'duración (min)', validators=[MinValueValidator(1, 'La duración debe ser mayor que 0.')],
    )
    precio = models.DecimalField(
        'precio ($)', max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), 'El precio debe ser mayor que 0.')],
    )
    # Un servicio desactivado ya no se ofrece al agendar, pero las citas pasadas lo conservan
    activo = models.BooleanField(default=True)
    veterinarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='servicios',
        blank=True,
        limit_choices_to={'rol': Roles.VETERINARIO},
    )

    # Clase que aporta metadatos al modelo
    class Meta:
        verbose_name = 'servicio'
        verbose_name_plural = 'servicios'
        ordering = ['nombre']
        constraints = [
            models.CheckConstraint(condition=models.Q(duracion_min__gt=0), name='servicio_duracion_positiva'),
            models.CheckConstraint(condition=models.Q(precio__gt=0), name='servicio_precio_positivo'),
        ]

    def __str__(self):
        return self.nombre


class HorarioVeterinario(models.Model):
    """Un bloque en que el veterinario atiende, por fecha concreta: si un día no atiende, no lo carga (HU-26).
    limit_choices_to también valida en full_clean() que el veterinario tenga ese rol."""
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='horarios',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField('hora de inicio')
    hora_fin = models.TimeField('hora de fin')

    # Clase que aporta metadatos al modelo
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
