"""El perfil profesional del veterinario: su especialidad y si el administrador ya lo verificó."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .roles import Roles


class PerfilVeterinario(models.Model):
    """
    Datos que solo tiene un veterinario (tabla perfil_veterinario del ER, simplificada).

    Solo los veterinarios verificados se ofrecen al agendar (§2.1 paso a). Un veterinario nuevo empieza
    sin verificar hasta que el administrador lo revisa.
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_veterinario',
        limit_choices_to={'rol': Roles.VETERINARIO},
    )
    especialidad = models.CharField(max_length=80, blank=True)
    anios_experiencia = models.PositiveSmallIntegerField('años de experiencia', null=True, blank=True)
    descripcion = models.TextField('descripción', blank=True)
    verificado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'perfil de veterinario'
        verbose_name_plural = 'perfiles de veterinario'

    def __str__(self):
        return f'Perfil de {self.usuario}'

    def clean(self):
        if self.usuario_id and self.usuario.rol != Roles.VETERINARIO:
            raise ValidationError('Solo un veterinario tiene perfil de veterinario.')
