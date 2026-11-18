"""
Modelos de la historia clínica (versión mínima del ER, decisión d14 del tablero), separados por tema.
Django los encuentra porque se importan aquí; el resto del código usa historial.models.<Modelo>.

- consulta: la consulta de una cita atendida y las líneas de su receta (Prescripcion).
- vacuna: el catálogo de vacunas y las que recibió cada mascota (VacunaAplicada).
- seguimiento: el check de cada día del tratamiento que marca el dueño (TomaDia).

Fuera por ahora: exámenes de laboratorio, catálogo de medicamentos y una marca por cada toma (va una por día).
"""
from .consulta import Consulta, Prescripcion
from .seguimiento import TomaDia
from .vacuna import Vacuna, VacunaAplicada

__all__ = ['Consulta', 'Prescripcion', 'TomaDia', 'Vacuna', 'VacunaAplicada']
