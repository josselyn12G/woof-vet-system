"""
Observer del caché: cuando el superadministrador cambia una especie o una raza, se borran las opciones guardadas
del formulario de la mascota. Se conectan en MascotasConfig.ready().
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from compartido.cache import olvidar

from .models import Especie, Raza
from .services.catalogo import CLAVE_OPCIONES


@receiver([post_save, post_delete], sender=Especie)
@receiver([post_save, post_delete], sender=Raza)
def olvidar_opciones_del_catalogo(**kwargs):
    olvidar(CLAVE_OPCIONES)
