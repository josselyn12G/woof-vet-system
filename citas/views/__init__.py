"""
Vistas de citas, separadas por tema como sus services. Solo reciben la petición, le piden los datos
o las reglas a los services y responden; urls.py las sigue usando como views.<Vista>.

- catalogo: los servicios de la clínica (administrador).
- horarios: Mi horario del veterinario y su versión para el superadministrador.
- agendar: el Core del cliente (agendar, calendario en JSON, Mis citas, cancelar y reprogramar).
- agenda: el Core del veterinario (agenda del día, cerrar citas y pacientes).
- gestion: todas las citas, los horarios y los indicadores de la agenda de la clínica.
- calificaciones: el cliente califica una cita atendida.
- perfil: el perfil del veterinario con su reputación.
- resenas: las opiniones que recibe el veterinario (Mis calificaciones) y las de la clínica (Reseñas).
"""
from .agenda import AgendaVeterinarioView, PacientesView, ResultadoCitaView
from .agendar import (
    AgendarCitaView, CancelarCitaView, DiasDisponiblesView, MisCitasView, ReprogramarCitaView, ReprogramarDiasView,
    ReprogramarHorasView, TurnosDelDiaView,
)
from .calificaciones import CalificarCitaView
from .catalogo import ServicioCreateView, ServicioDeleteView, ServicioEstadoView, ServicioListView, ServicioUpdateView
from .gestion import GestionCancelarCitaView, GestionCitasView, GestionHorariosView, IndicadoresView
from .perfil import PerfilVeterinarioView
from .resenas import MisCalificacionesView, ResenasView
from .horarios import (
    CopiarSemanaView, GestionCopiarSemanaView, GestionHorarioEditarView, GestionHorarioEliminarView,
    GestionHorarioView, GestionServiciosVeterinarioView, HorarioEditarView, HorarioEliminarView, MiHorarioView,
    MisServiciosView,
)

__all__ = [
    # catalogo
    'ServicioListView', 'ServicioCreateView', 'ServicioUpdateView', 'ServicioEstadoView', 'ServicioDeleteView',
    # horarios
    'MiHorarioView', 'HorarioEditarView', 'HorarioEliminarView', 'CopiarSemanaView', 'MisServiciosView',
    'GestionHorarioView', 'GestionHorarioEditarView', 'GestionHorarioEliminarView', 'GestionCopiarSemanaView',
    'GestionServiciosVeterinarioView',
    # agendar
    'AgendarCitaView', 'TurnosDelDiaView', 'DiasDisponiblesView', 'MisCitasView', 'CancelarCitaView',
    'ReprogramarCitaView', 'ReprogramarDiasView', 'ReprogramarHorasView',
    # calificaciones
    'CalificarCitaView',
    # perfil
    'PerfilVeterinarioView',
    # resenas
    'MisCalificacionesView', 'ResenasView',
    # agenda
    'AgendaVeterinarioView', 'ResultadoCitaView', 'PacientesView',
    # gestion
    'GestionCitasView', 'GestionCancelarCitaView', 'GestionHorariosView', 'IndicadoresView',
]
