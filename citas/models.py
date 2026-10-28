from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

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
