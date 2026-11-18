"""Los servicios que ofrece la clínica (consulta, vacunación...) y quién los atiende."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from cuentas.models import Roles


class Servicio(models.Model):
    """
    Representa un servicio que ofrece la clínica, como consulta general o vacunación.

    Su duración define el largo de cada turno al agendar y su precio se copia
    en la cita. Solo lo pueden atender los veterinarios asignados.
    """
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

    @property
    def icono(self):
        """Ícono de Bootstrap Icons según el tipo de servicio (para las tarjetas de citas)."""
        nombre = self.nombre.lower()
        if any(palabra in nombre for palabra in ('baño', 'corte', 'pelu', 'estética')):
            return 'bi-scissors'
        if 'vacun' in nombre:
            return 'bi-shield-plus'
        if any(palabra in nombre for palabra in ('cirug', 'operac')):
            return 'bi-bandaid'
        return 'bi-heart-pulse'
