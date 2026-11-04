from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import BooleanField, Case, ExpressionWrapper, Q, Value, When
from django.db.models.functions import Lower
from django.utils import timezone


# Validador: la fecha de nacimiento no puede ser futura
def validar_fecha_no_futura(fecha):
    if fecha and fecha > timezone.localdate():
        raise ValidationError('La fecha de nacimiento no puede ser futura.')


# Especies con estilo propio en el CSS (foto-mascota--gato...); las demás usan el de "otro"
ESTILOS_DE_ESPECIE = ('perro', 'gato')
# La raza de quien no tiene una definida (todas las especies con mamíferos la traen)
RAZA_MESTIZO = 'Mestizo'


class Especie(models.Model):
    """
    Una especie que atiende la clínica (perro, gato, conejo...). Vive en la base, no en el código:
    el superadministrador agrega las que falten. La lista inicial la carga una migración.
    """
    nombre = models.CharField(max_length=40, unique=True)
    plural = models.CharField(max_length=40)   # "Peces", "Hámsters": para los filtros y las cifras
    # Identificador fijo para las URLs (?especie=gato) y las clases del CSS
    codigo = models.SlugField(max_length=30, unique=True)
    orden = models.PositiveSmallIntegerField(default=50, help_text='Las de número menor salen primero.')
    # Una especie desactivada ya no se ofrece al registrar, pero las mascotas que la tienen la conservan
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'especie'
        verbose_name_plural = 'especies'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    @property
    def estilo(self):
        """El sufijo de las clases del CSS: foto-mascota--gato, punto-especie--otro..."""
        return self.codigo if self.codigo in ESTILOS_DE_ESPECIE else 'otro'


class RazaQuerySet(models.QuerySet):
    def mestizo_primero(self):
        """Por especie y, dentro de cada una, Mestizo arriba de todo (es la más elegida) y el resto por nombre."""
        return self.order_by(
            'especie__orden', 'especie__nombre', Case(When(nombre=RAZA_MESTIZO, then=Value(0)), default=Value(1)),
            'nombre',
        )


class Raza(models.Model):
    """Una raza de una especie. No se repite el nombre dentro de la misma especie (sin importar mayúsculas)."""
    especie = models.ForeignKey(Especie, on_delete=models.CASCADE, related_name='razas')
    nombre = models.CharField(max_length=60)
    activa = models.BooleanField(default=True)

    objects = RazaQuerySet.as_manager()

    class Meta:
        verbose_name = 'raza'
        verbose_name_plural = 'razas'
        ordering = ['especie__orden', 'nombre']
        constraints = [
            models.UniqueConstraint(Lower('nombre'), 'especie', name='raza_unica_por_especie'),
        ]

    def __str__(self):
        return self.nombre


class Sexos(models.TextChoices):
    MACHO = 'M', 'Macho'
    HEMBRA = 'H', 'Hembra'


class MascotaQuerySet(models.QuerySet):
    def con_foto(self):
        """Sin traer los bytes de la foto (defer), pero sabiendo si tiene una: tiene_foto basta para mostrarla.
        Trae también la especie y la raza, que se muestran en todas las tarjetas."""
        return self.select_related('especie', 'raza').defer('foto').annotate(
            tiene_foto=ExpressionWrapper(Q(foto__isnull=False), output_field=BooleanField()),
        )

    def del_dueno(self, dueno):
        return self.filter(dueno=dueno)


class Mascota(models.Model):
    # El dueño no va en el formulario: la vista lo toma de request.user
    dueno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mascotas',
        verbose_name='dueño',
    )
    nombre = models.CharField(max_length=60)
    # PROTECT: una especie o una raza con mascotas no se borra (se desactiva)
    especie = models.ForeignKey(Especie, on_delete=models.PROTECT, related_name='mascotas')
    raza = models.ForeignKey(Raza, on_delete=models.PROTECT, related_name='mascotas', null=True, blank=True)
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

    objects = MascotaQuerySet.as_manager()

    # Clase que aporta metadatos al modelo
    class Meta:
        verbose_name = 'mascota'
        verbose_name_plural = 'mascotas'
        ordering = ['nombre']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(peso_kg__isnull=True) | models.Q(peso_kg__gt=0),
                name='mascota_peso_positivo',
            ),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        # La raza tiene que ser de la especie elegida (un "Siamés" no puede ser perro)
        if self.raza_id and self.especie_id and self.raza.especie_id != self.especie_id:
            raise ValidationError({'raza': 'Esa raza no es de la especie elegida.'})

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
