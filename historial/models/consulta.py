"""La consulta que registra el veterinario después de una cita atendida, y las líneas de su receta."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from citas.models import EstadoCita
from cuentas.models import Roles


class Consulta(models.Model):
    """
    Lo que pasó en una visita: motivo, peso, diagnóstico e indicaciones para el dueño (RF-20).

    Nace de una cita atendida, una sola por cita (OneToOne). Como en el ER, la cita es opcional para
    una emergencia sin reserva; la mascota y el veterinario se guardan aparte para leer la historia rápido.
    """
    # PROTECT: una cita con consulta no se borra (de todas formas las citas no se borran: cambian de estado)
    cita = models.OneToOneField(
        'citas.Cita', on_delete=models.PROTECT, related_name='consulta', null=True, blank=True,
    )
    mascota = models.ForeignKey('mascotas.Mascota', on_delete=models.CASCADE, related_name='consultas')
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='consultas_registradas',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    fecha = models.DateTimeField(default=timezone.now)
    motivo = models.CharField(max_length=200, blank=True)
    peso_kg = models.DecimalField(
        'peso (kg)', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'), 'El peso debe ser mayor que 0.')],
    )
    diagnostico = models.TextField('diagnóstico')
    indicaciones = models.TextField('indicaciones para el dueño', blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'consulta'
        verbose_name_plural = 'consultas'
        ordering = ['-fecha']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(peso_kg__isnull=True) | models.Q(peso_kg__gt=0),
                name='consulta_peso_positivo',
            ),
        ]

    def __str__(self):
        return f'{self.mascota} · {timezone.localtime(self.fecha):%d/%m/%Y}'

    def clean(self):
        """La consulta de una cita: solo si está atendida, y con su misma mascota y su mismo veterinario."""
        if not self.cita_id:
            return
        if self.cita.estado != EstadoCita.ATENDIDA:
            raise ValidationError('Solo se registra la consulta de una cita atendida.')
        if self.mascota_id and self.mascota_id != self.cita.mascota_id:
            raise ValidationError({'mascota': 'La mascota debe ser la de la cita.'})
        if self.veterinario_id and self.veterinario_id != self.cita.veterinario_id:
            raise ValidationError({'veterinario': 'Solo el veterinario de la cita registra su consulta.'})


class Prescripcion(models.Model):
    """
    Una línea de la receta: qué medicamento, cuánto, cada cuántas horas y por cuántos días.

    El medicamento va como texto (sin catálogo) y las tomas no se guardan una por una:
    se calcula cuántas son para mostrarlo al veterinario y al dueño.
    """
    consulta = models.ForeignKey(Consulta, on_delete=models.CASCADE, related_name='prescripciones')
    medicamento = models.CharField(max_length=120)
    dosis = models.CharField(max_length=60, help_text='Por ejemplo: 1 tableta, 5 ml.')
    frecuencia_horas = models.PositiveSmallIntegerField(
        'cada (horas)', validators=[MinValueValidator(1, 'La frecuencia debe ser de al menos 1 hora.')],
    )
    duracion_dias = models.PositiveSmallIntegerField(
        'durante (días)', validators=[MinValueValidator(1, 'La duración debe ser de al menos 1 día.')],
    )
    fecha_inicio = models.DateTimeField('desde', default=timezone.now)
    indicaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'prescripción'
        verbose_name_plural = 'prescripciones'
        ordering = ['pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(frecuencia_horas__gt=0), name='prescripcion_frecuencia_positiva'),
            models.CheckConstraint(condition=models.Q(duracion_dias__gt=0), name='prescripcion_duracion_positiva'),
        ]

    def __str__(self):
        return f'{self.medicamento} · {self.dosis} cada {self.frecuencia_horas} h'

    @property
    def tomas(self):
        """Cuántas tomas salen: 7 días cada 12 horas son 14 (las horas del tratamiento entre la frecuencia)."""
        return self.duracion_dias * 24 // self.frecuencia_horas

    @property
    def termina(self):
        """Cuándo se acaba el tratamiento: la fecha de inicio más los días que dura."""
        return self.fecha_inicio + timedelta(days=self.duracion_dias)

    @property
    def en_curso(self):
        """Si el dueño todavía tiene que dárselo: ya empezó y aún no terminó."""
        return self.fecha_inicio <= timezone.now() < self.termina

    @property
    def dia_actual(self):
        """En qué día del tratamiento va (1, 2, ...), para el «Día 2 de 7» del dueño."""
        return min((timezone.now() - self.fecha_inicio).days + 1, self.duracion_dias)

    @property
    def progreso(self):
        """Qué parte del tratamiento ya pasó, de 0 a 100, para la barrita de avance."""
        return round(self.dia_actual * 100 / self.duracion_dias)
