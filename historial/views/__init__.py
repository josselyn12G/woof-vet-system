"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
- historia: ver la historia clínica de una mascota (cliente, veterinario y administrador).
- vacunas: el catálogo de vacunas (administrador).
"""
from .consulta import RegistrarConsultaView
from .historia import HistoriaClinicaView
from .vacunas import VacunaCreateView, VacunaEstadoView, VacunaListView, VacunaUpdateView

__all__ = [
    'RegistrarConsultaView', 'HistoriaClinicaView',
    'VacunaListView', 'VacunaCreateView', 'VacunaUpdateView', 'VacunaEstadoView',
]
