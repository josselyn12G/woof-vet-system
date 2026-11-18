"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
- historia: ver la historia clínica de una mascota (cliente, veterinario y administrador)
  y «Historial médico», la lista de historias del cliente.
- vacunas: el catálogo de vacunas (administrador).
"""
from .consulta import RegistrarConsultaView
from .historia import HistoriaClinicaView, MisHistorialesView
from .vacunas import VacunaCreateView, VacunaEstadoView, VacunaListView, VacunaUpdateView

__all__ = [
    'RegistrarConsultaView', 'HistoriaClinicaView', 'MisHistorialesView',
    'VacunaListView', 'VacunaCreateView', 'VacunaUpdateView', 'VacunaEstadoView',
]
