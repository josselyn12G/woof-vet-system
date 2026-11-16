"""El catálogo de vacunas y las que recibió cada mascota (su carnet de vacunación)."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from cuentas.models import Roles


class Vacuna(models.Model):
    """
    Una vacuna que aplica la clínica (Rabia, Polivalente canina...). Vive en la base como el
    catálogo de especies: se desactiva en vez de borrarse y las mascotas vacunadas la conservan.

    Sin especie, sirve para cualquiera. Con refuerzo_cada_dias, la próxima dosis se calcula sola.
    """
    nombre = models.CharField(max_length=80)
    # Vacía = para todas las especies. PROTECT: una especie con vacunas no se borra (se desactiva)
    especie = models.ForeignKey(
        'mascotas.Especie', on_delete=models.PROTECT, related_name='vacunas', null=True, blank=True,
    )
    refuerzo_cada_dias = models.PositiveSmallIntegerField(
        'refuerzo cada (días)', null=True, blank=True,
        validators=[MinValueValidator(1, 'El refuerzo debe ser de al menos 1 día.')],
        help_text='Vacío si no lleva refuerzo.',
    )
    # Una vacuna desactivada ya no se ofrece al registrar, pero el carnet sigue mostrándola
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'vacuna'
        verbose_name_plural = 'vacunas'
        ordering = ['nombre']
        constraints = [
            # "Rabia" puede estar para perro y para gato, pero no dos veces para la misma especie
            models.UniqueConstraint(Lower('nombre'), 'especie', name='vacuna_unica_por_especie'),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.especie})' if self.especie_id else self.nombre

    def sirve_para(self, especie):
        return self.especie_id is None or self.especie_id == especie.pk


class VacunaAplicada(models.Model):
    """
    Una dosis aplicada a una mascota: la línea del carnet de vacunación (HU-36).

    Se registra desde una consulta (o sola, si se carga una vacuna de antes). La próxima dosis
    es la fecha de aplicación más el refuerzo de la vacuna, si lo tiene.
    """
    mascota = models.ForeignKey('mascotas.Mascota', on_delete=models.CASCADE, related_name='vacunas_aplicadas')
    # PROTECT: una vacuna que ya se aplicó no se borra del catálogo (se desactiva)
    vacuna = models.ForeignKey(Vacuna, on_delete=models.PROTECT, related_name='aplicaciones')
    consulta = models.ForeignKey(
        'historial.Consulta', on_delete=models.CASCADE, related_name='vacunas_aplicadas', null=True, blank=True,
    )
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='vacunas_aplicadas',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    fecha_aplicacion = models.DateField('fecha de aplicación', default=timezone.localdate)
    lote = models.CharField(max_length=40, blank=True)
    proxima_dosis = models.DateField('próxima dosis', null=True, blank=True)

    class Meta:
        verbose_name = 'vacuna aplicada'
        verbose_name_plural = 'vacunas aplicadas'
        ordering = ['-fecha_aplicacion', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(proxima_dosis__isnull=True) | models.Q(proxima_dosis__gt=models.F('fecha_aplicacion')),
                name='vacuna_proxima_dosis_despues',
            ),
        ]

    def __str__(self):
        return f'{self.vacuna.nombre} · {self.mascota} · {self.fecha_aplicacion:%d/%m/%Y}'

    def calcular_proxima_dosis(self):
        """Fecha de aplicación + refuerzo de la vacuna; None si la vacuna no lleva refuerzo."""
        if self.vacuna.refuerzo_cada_dias:
            return self.fecha_aplicacion + timedelta(days=self.vacuna.refuerzo_cada_dias)
        return None

    def clean(self):
        if self.fecha_aplicacion and self.fecha_aplicacion > timezone.localdate():
            raise ValidationError({'fecha_aplicacion': 'La fecha de aplicación no puede ser futura.'})
        if self.vacuna_id and self.mascota_id and not self.vacuna.sirve_para(self.mascota.especie):
            raise ValidationError({'vacuna': f'Esa vacuna es para {self.vacuna.especie}, no para esta mascota.'})

    def save(self, *args, **kwargs):
        # Si no se escribió la próxima dosis, se calcula con el refuerzo de la vacuna
        if self.proxima_dosis is None:
            self.proxima_dosis = self.calcular_proxima_dosis()
        super().save(*args, **kwargs)
