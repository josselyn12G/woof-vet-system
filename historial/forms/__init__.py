"""
Formularios de la historia clínica, separados por tema como en citas/forms.

- consulta: la consulta, su receta y las vacunas aplicadas (registrar consulta, RF-20).
"""
from .consulta import ConsultaForm, PrescripcionForm, RecetaFormSet, VacunaAplicadaForm, VacunasFormSet

__all__ = ['ConsultaForm', 'PrescripcionForm', 'RecetaFormSet', 'VacunaAplicadaForm', 'VacunasFormSet']
