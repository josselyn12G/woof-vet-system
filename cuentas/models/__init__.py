"""
Modelos de cuentas, separados por tema como en citas y mascotas.
Django los encuentra porque se importan aquí; el resto del código sigue usando cuentas.models.<Nombre>.

- roles: los roles y los grupos de roles que usan los permisos.
- usuario: el Usuario de Woof y su UsuarioManager (la migración 0001 lo usa como cuentas.models.UsuarioManager).
"""
from .roles import ROLES_DE_GESTION, ROLES_DEL_PERSONAL, Roles
from .usuario import Usuario, UsuarioManager, validar_telefono

__all__ = ['ROLES_DE_GESTION', 'ROLES_DEL_PERSONAL', 'Roles', 'Usuario', 'UsuarioManager', 'validar_telefono']
