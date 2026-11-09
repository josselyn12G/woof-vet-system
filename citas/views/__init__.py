"""
Vistas de citas, separadas por tema como sus services. Solo reciben la petición, le piden los datos
o las reglas a los services y responden; urls.py las sigue usando como views.<Vista>.

- catalogo: los servicios de la clínica (administrador).
- horarios: Mi horario del veterinario y su versión para el superadministrador.
- agendar: el Core del cliente (agendar, calendario en JSON, Mis citas y cancelar).
- agenda: el Core del veterinario (agenda del día, cerrar citas y pacientes).
- gestion: todas las citas y los horarios de la clínica.
"""
from .agenda import AgendaVeterinarioView, PacientesView, ResultadoCitaView
from .agendar import AgendarCitaView, CancelarCitaView, DiasDisponiblesView, MisCitasView, TurnosDelDiaView
from .catalogo import ServicioCreateView, ServicioDeleteView, ServicioEstadoView, ServicioListView, ServicioUpdateView
from .gestion import GestionCancelarCitaView, GestionCitasView, GestionHorariosView
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
    # agenda
    'AgendaVeterinarioView', 'ResultadoCitaView', 'PacientesView',
    # gestion
    'GestionCitasView', 'GestionCancelarCitaView', 'GestionHorariosView',
]
