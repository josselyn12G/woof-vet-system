"""Dónde vive cada usuario: país → provincia → ciudad (los desplegables dependientes del registro)."""
from django.db import models
from django.db.models.functions import Lower


class Pais(models.Model):
    """Un país. La lista inicial (Ecuador) la carga una migración; se pueden agregar otros desde /admin/."""
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name = 'país'
        verbose_name_plural = 'países'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Provincia(models.Model):
    """Una provincia de un país. El nombre no se repite dentro del mismo país."""
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE, related_name='provincias', verbose_name='país')
    nombre = models.CharField(max_length=60)

    class Meta:
        verbose_name = 'provincia'
        verbose_name_plural = 'provincias'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(Lower('nombre'), 'pais', name='provincia_unica_por_pais'),
        ]

    def __str__(self):
        return self.nombre


class Ciudad(models.Model):
    """Una ciudad de una provincia. El nombre no se repite dentro de la misma provincia."""
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE, related_name='ciudades')
    nombre = models.CharField(max_length=80)

    class Meta:
        verbose_name = 'ciudad'
        verbose_name_plural = 'ciudades'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(Lower('nombre'), 'provincia', name='ciudad_unica_por_provincia'),
        ]

    def __str__(self):
        return self.nombre
