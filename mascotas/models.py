from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# Validador: la fecha de nacimiento no puede ser futura
def validar_fecha_no_futura(fecha):
    if fecha and fecha > timezone.localdate():
        raise ValidationError('La fecha de nacimiento no puede ser futura.')


# Opciones fijas para la especie y el sexo
class Especies(models.TextChoices):
    PERRO = 'perro', 'Perro'
    GATO = 'gato', 'Gato'
    OTRO = 'otro', 'Otro'


class Sexos(models.TextChoices):
    MACHO = 'M', 'Macho'
    HEMBRA = 'H', 'Hembra'


class Mascota(models.Model):
    # El dueño no va en el formulario: la vista lo toma de request.user
    dueno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mascotas',
        verbose_name='dueño',
    )
    nombre = models.CharField(max_length=60)
    especie = models.CharField(max_length=10, choices=Especies.choices)
    raza = models.CharField(max_length=60, blank=True)
    sexo = models.CharField(max_length=1, choices=Sexos.choices, blank=True)
    fecha_nacimiento = models.DateField(
        'fecha de nacimiento', null=True, blank=True, validators=[validar_fecha_no_futura],
    )
    peso_kg = models.DecimalField(
        'peso (kg)', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'), 'El peso debe ser mayor que 0.')],
    )
    # La foto se guarda dentro de la base (Neon), ya reducida a WEBP: así la ve cualquiera que use
    # la misma base, sin depender de archivos en una computadora. La entrega la vista FotoMascotaView
    foto = models.BinaryField(null=True, blank=True, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    # Clase que aporta metadatos al modelo
    class Meta:
        verbose_name = 'mascota'
        verbose_name_plural = 'mascotas'
        ordering = ['nombre']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(especie__in=Especies.values),
                name='mascota_especie_valida',
            ),
            models.CheckConstraint(
                condition=models.Q(peso_kg__isnull=True) | models.Q(peso_kg__gt=0),
                name='mascota_peso_positivo',
            ),
        ]

    def __str__(self):
        return self.nombre

    # Edad en texto ("2 años y 3 meses"); None si no se registró la fecha de nacimiento
    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None

        hoy = timezone.localdate()
        meses = (hoy.year - self.fecha_nacimiento.year) * 12 + hoy.month - self.fecha_nacimiento.month
        if hoy.day < self.fecha_nacimiento.day:
            meses -= 1  # todavía no cumple el mes en curso
        anios, meses = divmod(max(meses, 0), 12)

        partes = []
        if anios:
            partes.append(f'{anios} año{"s" if anios != 1 else ""}')
        if meses:
            partes.append(f'{meses} mes{"es" if meses != 1 else ""}')
        return ' y '.join(partes) or 'Menos de un mes'
