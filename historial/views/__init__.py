"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
- historia: ver la historia clínica de una mascota (cliente, veterinario y administrador).
- vacunas: el catálogo de vacunas (administrador).
- cliente: Historia clínica y Mis recetas del menú del cliente.
"""
from .cliente import MarcarDiaView, MiHistoriaClinicaView, MisRecetasView, TratamientoView
from .consulta import RegistrarConsultaView
from .historia import HistoriaClinicaView, HistoriaPdfView
from .vacunas import VacunaCreateView, VacunaEstadoView, VacunaListView, VacunaUpdateView

__all__ = [
    'RegistrarConsultaView', 'HistoriaClinicaView', 'HistoriaPdfView', 'MiHistoriaClinicaView', 'MisRecetasView',
    'TratamientoView', 'MarcarDiaView',
    'VacunaListView', 'VacunaCreateView', 'VacunaUpdateView', 'VacunaEstadoView',
]
