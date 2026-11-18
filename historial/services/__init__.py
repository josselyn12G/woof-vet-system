"""
Lógica de la historia clínica fuera de las vistas, como en citas/services.

- historial: las consultas y vacunas de una mascota, y qué se le puede registrar.
- catalogo: el catálogo de vacunas que gestiona el administrador.
- veterinario: las páginas Consultas médicas y Vacunación del veterinario.
"""
from .catalogo import VacunaCatalogoService
from .historial import HistorialService
from .veterinario import ClinicaDelVeterinarioService

__all__ = ['HistorialService', 'VacunaCatalogoService', 'ClinicaDelVeterinarioService']
