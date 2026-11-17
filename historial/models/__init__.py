"""
Modelos de la historia clínica (versión mínima del ER, decisión d14 del tablero), separados por tema.
Django los encuentra porque se importan aquí; el resto del código usa historial.models.<Modelo>.

- consulta: la consulta de una cita atendida y las líneas de su receta (Prescripcion).
- vacuna: el catálogo de vacunas y las que recibió cada mascota (VacunaAplicada).

Fuera por ahora: exámenes de laboratorio, catálogo de medicamentos y tomas programadas.
"""
from .consulta import Consulta, Prescripcion
from .vacuna import Vacuna, VacunaAplicada

__all__ = ['Consulta', 'Prescripcion', 'Vacuna', 'VacunaAplicada']
