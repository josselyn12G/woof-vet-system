"""
Lógica de la historia clínica fuera de las vistas, como en citas/services.

- historial: las consultas y vacunas de una mascota, y qué se le puede registrar.
"""
from .historial import HistorialService

__all__ = ['HistorialService']
