"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
- historia: ver la historia clínica de una mascota (cliente, veterinario y administrador).
"""
from .consulta import RegistrarConsultaView
from .historia import HistoriaClinicaView

__all__ = ['RegistrarConsultaView', 'HistoriaClinicaView']
