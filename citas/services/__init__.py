"""
Lógica de citas fuera de las vistas: las vistas reciben la petición, piden los datos aquí y dibujan la plantilla.

- agenda: las reglas del Core (turnos libres, agendar, cancelar y cerrar una cita).
- catalogo: el catálogo de servicios.
- horarios: Mi horario del veterinario y los horarios de la clínica.
- consultas: las citas que muestra cada pantalla (Mis citas, la agenda y la gestión).
- estadisticas: las cifras de la portada del veterinario.
"""
from .agenda import TURNO_OCUPADO, AgendaService
from .catalogo import ESTADOS_SERVICIO, ServicioService
from .consultas import VISTAS_CITAS, VISTAS_GESTION, CitaService
from .estadisticas import EstadisticasService
from .horarios import HorarioService

__all__ = [
    'AgendaService', 'CitaService', 'ESTADOS_SERVICIO', 'EstadisticasService', 'HorarioService', 'ServicioService',
    'TURNO_OCUPADO', 'VISTAS_CITAS', 'VISTAS_GESTION',
]
