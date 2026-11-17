"""
Lógica de la historia clínica fuera de las vistas, como en citas/services.

- historial: las consultas y vacunas de una mascota, y qué se le puede registrar.
- catalogo: el catálogo de vacunas que gestiona el administrador.
"""
from .catalogo import VacunaCatalogoService
from .historial import HistorialService

__all__ = ['HistorialService', 'VacunaCatalogoService']
