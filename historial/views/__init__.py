"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
"""
from .consulta import RegistrarConsultaView

__all__ = ['RegistrarConsultaView']
