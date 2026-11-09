"""
Vistas de cuentas, separadas por tema como sus formularios y services. Solo reciben la petición, le piden
los datos o las reglas a los services y responden; urls.py las sigue usando como views.<Vista>.

- acceso: la portada, el registro y el login en dos pasos.
- usuarios: los usuarios de la clínica (administrador).
- equipo: el personal de la clínica (superadministrador).
"""
from .acceso import InicioView, LoginDosPasosView, RegistroView, VerificarView
from .equipo import EquipoContrasenaView, EquipoCrearView, EquipoEditarView, EquipoEstadoView, EquipoListView
from .usuarios import ReporteUsuariosView, UsuarioEditarView, UsuarioListView

__all__ = [
    # acceso
    'InicioView', 'RegistroView', 'LoginDosPasosView', 'VerificarView',
    # usuarios
    'UsuarioListView', 'ReporteUsuariosView', 'UsuarioEditarView',
    # equipo
    'EquipoListView', 'EquipoCrearView', 'EquipoEditarView', 'EquipoContrasenaView', 'EquipoEstadoView',
]
