"""
Observer del caché: cuando cambia una provincia o una ciudad, se borra el árbol de ubicación guardado.

Las señales post_save y post_delete de Django son el patrón Observer: el modelo no sabe quién escucha;
este archivo se suscribe y reacciona. Se conectan en CuentasConfig.ready().
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from compartido.cache import olvidar

from .models import Ciudad, Pais, Provincia
from .services.ubicacion import CLAVE_ARBOL


@receiver([post_save, post_delete], sender=Pais)
@receiver([post_save, post_delete], sender=Provincia)
@receiver([post_save, post_delete], sender=Ciudad)
def olvidar_ubicacion(**kwargs):
    olvidar(CLAVE_ARBOL)
