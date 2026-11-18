"""
Vistas de la historia clínica, separadas por tema como en citas/views.

- consulta: registrar la consulta de una cita atendida (veterinario, RF-20).
- historia: ver la historia clínica de una mascota (cliente, veterinario y administrador)
  y «Historial médico», la lista de historias del cliente.
- vacunas: el catálogo de vacunas (administrador).
- cliente: Historia clínica y Mis recetas del menú del cliente.
"""
from .cliente import GuardarDiasView, MarcarDiaView, MiHistoriaClinicaView, MisRecetasView, TratamientoView
from .consulta import RegistrarConsultaView
from .historia import HistoriaClinicaView, HistoriaPdfView, MisHistorialesView
from .vacunas import VacunaCreateView, VacunaEstadoView, VacunaListView, VacunaUpdateView
from .veterinario import ConsultasVeterinarioView, VacunacionVeterinarioView

__all__ = [
    'RegistrarConsultaView', 'HistoriaClinicaView', 'HistoriaPdfView', 'MisHistorialesView', 'MiHistoriaClinicaView',
    'MisRecetasView', 'TratamientoView', 'MarcarDiaView', 'GuardarDiasView',
    'VacunaListView', 'VacunaCreateView', 'VacunaUpdateView', 'VacunaEstadoView',
    'ConsultasVeterinarioView', 'VacunacionVeterinarioView',
]
