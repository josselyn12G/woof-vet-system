"""El catálogo de especies y razas: vive en la base y lo edita el superadministrador."""
from django.db import models
from django.db.models import Case, Value, When
from django.db.models.functions import Lower

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
