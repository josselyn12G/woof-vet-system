"""
Formularios de la historia clínica, separados por tema como en citas/forms.

- consulta: la consulta, su receta y las vacunas aplicadas (registrar consulta, RF-20).
- vacunas: una vacuna del catálogo (administrador).
"""
from .consulta import ConsultaForm, PrescripcionForm, RecetaFormSet, VacunaAplicadaForm, VacunasFormSet
from .vacunas import VacunaForm

__all__ = ['ConsultaForm', 'PrescripcionForm', 'RecetaFormSet', 'VacunaAplicadaForm', 'VacunasFormSet', 'VacunaForm']
