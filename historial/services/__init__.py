"""
Lógica de la historia clínica fuera de las vistas, como en citas/services.

- historial: la historia clínica de una mascota (consultas, tablero) y registrar una consulta.
- carnet: el carnet de vacunación y las vacunas que se le pueden aplicar.
- tratamiento: las recetas, el check por día del tratamiento y Mis recetas.
- catalogo: el catálogo de vacunas que gestiona el administrador.
- veterinario: las páginas Consultas médicas y Vacunación del veterinario.
"""
from .carnet import CarnetService
from .catalogo import VacunaCatalogoService
from .historial import HistorialService
from .tratamiento import TratamientoService
from .veterinario import ClinicaDelVeterinarioService

__all__ = [
    'CarnetService', 'ClinicaDelVeterinarioService', 'HistorialService', 'TratamientoService', 'VacunaCatalogoService',
]
