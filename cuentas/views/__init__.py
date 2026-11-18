"""
Vistas de cuentas, separadas por tema como sus formularios y services. Solo reciben la petición, le piden
los datos o las reglas a los services y responden; urls.py las sigue usando como views.<Vista>.

- acceso: la portada, el registro y el login en dos pasos.
- cuenta: Mi cuenta, cambiar la contraseña, verificar el correo y los términos.
- usuarios: los usuarios de la clínica (administrador).
- equipo: el personal de la clínica (superadministrador).
- ubicacion: provincias y ciudades en JSON para los desplegables del registro.
"""
from .acceso import InicioView, LoginDosPasosView, RegistroView, VerificarView
from .cuenta import CambiarContrasenaView, MiCuentaView, ReenviarVerificacionView, TerminosView, VerificarCorreoView
from .equipo import EquipoContrasenaView, EquipoCrearView, EquipoEditarView, EquipoEstadoView, EquipoListView
from .ubicacion import CiudadesView, ProvinciasView
from .usuarios import ReporteUsuariosView, UsuarioEditarView, UsuarioListView

__all__ = [
    # acceso
    'InicioView', 'RegistroView', 'LoginDosPasosView', 'VerificarView',
    # cuenta
    'MiCuentaView', 'CambiarContrasenaView', 'ReenviarVerificacionView', 'VerificarCorreoView', 'TerminosView',
    # ubicacion
    'ProvinciasView', 'CiudadesView',
    # usuarios
    'UsuarioListView', 'ReporteUsuariosView', 'UsuarioEditarView',
    # equipo
    'EquipoListView', 'EquipoCrearView', 'EquipoEditarView', 'EquipoContrasenaView', 'EquipoEstadoView',
]
