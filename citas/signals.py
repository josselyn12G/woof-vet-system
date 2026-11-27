"""
Observer del caché: borra la lista de servicios agendables cuando cambia algo de lo que depende.

Un servicio se puede agendar si está activo y lo atiende algún veterinario activo y verificado, así que la lista
se borra cuando cambia un servicio, la lista de veterinarios que lo atienden (m2m_changed), el perfil de un
veterinario (su verificación) o una cuenta (si se desactiva). Se conectan en CitasConfig.ready().
"""
from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from compartido.cache import olvidar
from cuentas.models import PerfilVeterinario

from .models import Servicio
from .services.catalogo import CLAVE_AGENDABLES


@receiver([post_save, post_delete], sender=Servicio)
@receiver([post_save, post_delete], sender=PerfilVeterinario)
@receiver(m2m_changed, sender=Servicio.veterinarios.through)
def olvidar_servicios_agendables(**kwargs):
    olvidar(CLAVE_AGENDABLES)


@receiver(post_save, sender=get_user_model())
def olvidar_servicios_si_cambia_una_cuenta(update_fields=None, **kwargs):
    # Iniciar sesión guarda solo last_login: eso no cambia quién atiende, así que no hace falta borrar nada
    if update_fields is not None and set(update_fields) == {'last_login'}:
        return
    olvidar(CLAVE_AGENDABLES)
