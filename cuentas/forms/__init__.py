"""
Formularios de cuentas, separados por tema. Solo validan la entrada; la regla de qué rol puede dar
cada persona se la piden a PoliticaDeCuentas (services).

- comunes: etiquetas de los campos y el estilo del panel (también lo usan los formularios de mascotas).
- acceso: el registro y el código del login en dos pasos.
- usuarios: el rol que da el administrador y el equipo del superadministrador.
- perfil: la especialidad y la verificación del veterinario.
"""
from .acceso import RegistroForm, VerificarCodigoForm
from .comunes import CEDULA, ETIQUETAS, con_estilo_del_panel
from .perfil import PerfilVeterinarioForm
from .usuarios import (
    NuevaContrasenaForm, PersonalCreacionForm, PersonalForm, RolSegunQuienEditaMixin, UsuarioRolForm,
)

__all__ = [
    'CEDULA', 'ETIQUETAS', 'NuevaContrasenaForm', 'PerfilVeterinarioForm', 'PersonalCreacionForm', 'PersonalForm',
    'RegistroForm', 'RolSegunQuienEditaMixin', 'UsuarioRolForm', 'VerificarCodigoForm', 'con_estilo_del_panel',
]
