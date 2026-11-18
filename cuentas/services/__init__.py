"""
Lógica de cuentas fuera de las vistas.

- doble_factor: el login en dos pasos y el código de 6 dígitos que se envía al correo.
- usuarios: búsquedas de cuentas y la política de quién gestiona a quién (administrador y superadministrador).
- perfiles: el perfil del veterinario y el filtro de veterinarios verificados.
- ubicacion: país → provincia → ciudad (listas de los desplegables y que encajen entre sí).
- verificacion: el enlace para verificar el correo (HU-13).
"""
from .doble_factor import (
    cancelar_login_pendiente, completar_login, enviar_codigo, generar_codigo, hay_login_pendiente,
    iniciar_login_pendiente, verificar_codigo,
)
from .perfiles import VERIFICADO, PerfilVeterinarioService
from .ubicacion import UbicacionService
from .usuarios import PoliticaDeCuentas, UsuarioService
from .verificacion import enviar_verificacion, verificar_correo

__all__ = [
    'PerfilVeterinarioService', 'PoliticaDeCuentas', 'UbicacionService', 'UsuarioService', 'VERIFICADO',
    'cancelar_login_pendiente', 'completar_login', 'enviar_codigo', 'generar_codigo', 'hay_login_pendiente',
    'enviar_verificacion', 'iniciar_login_pendiente', 'verificar_codigo', 'verificar_correo',
]
