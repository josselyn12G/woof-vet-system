"""Los roles de Woof y los grupos que usan los permisos (quién gestiona la clínica, quién es personal)."""
from django.db import models


# Opciones fijas para los roles ya definidos
class Roles(models.TextChoices):
    CLIENTE = 'cliente', 'Cliente'
    VETERINARIO = 'veterinario', 'Veterinario'
    ADMINISTRADOR = 'administrador', 'Administrador'
    SUPERADMIN = 'superadmin', 'Superadministrador'


# Roles que administran la clínica: el superadministrador puede todo lo que hace un administrador
ROLES_DE_GESTION = (Roles.ADMINISTRADOR, Roles.SUPERADMIN)
# Cuentas del personal (las que gestiona el superadministrador)
ROLES_DEL_PERSONAL = (Roles.VETERINARIO, Roles.ADMINISTRADOR, Roles.SUPERADMIN)
