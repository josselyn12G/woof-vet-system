"""Registrar consulta (RF-20): los datos de la consulta, las líneas de la receta y las vacunas aplicadas."""
from django import forms
from django.db.models import Q

from ..models import Consulta, Prescripcion, Vacuna, VacunaAplicada
from ..services import HistorialService


def area(filas, placeholder=''):
    return forms.Textarea(attrs={'rows': filas, 'class': 'control-panel', 'placeholder': placeholder})


def texto(placeholder=''):
    return forms.TextInput(attrs={'class': 'control-panel', 'placeholder': placeholder})


class ConsultaForm(forms.ModelForm):
    """
    Lo que escribe el veterinario. La cita, la mascota, el veterinario y la fecha no van en el formulario:
    la vista los pone en la instancia antes de validar, así clean() del modelo revisa que la cita esté atendida.
    """

    class Meta:
        model = Consulta
        fields = ['motivo', 'peso_kg', 'diagnostico', 'indicaciones']
        widgets = {
            'motivo': texto('Por qué vino hoy'),
            'peso_kg': forms.NumberInput(attrs={'class': 'control-panel', 'step': '0.01', 'min': '0.01',
                                                'placeholder': 'Ej.: 12,6'}),
            'diagnostico': area(4, 'Lo que encontraste en la revisión'),
            'indicaciones': area(4, 'Cuidados en casa, cuándo volver a control...'),
        }
        labels = {'peso_kg': 'Peso hoy (kg)'}


class PrescripcionForm(forms.ModelForm):
    """Una línea de la receta. La fecha de inicio queda en la de la consulta (el default del modelo)."""

    class Meta:
        model = Prescripcion
        fields = ['medicamento', 'dosis', 'frecuencia_horas', 'duracion_dias', 'indicaciones']
        widgets = {
            'medicamento': texto('Ej.: Amoxicilina 250 mg'),
            'dosis': texto('Ej.: 1 tableta, 5 ml'),
            'frecuencia_horas': forms.NumberInput(attrs={'class': 'control-panel', 'min': '1', 'placeholder': '12',
                                                         'data-frecuencia': ''}),
            'duracion_dias': forms.NumberInput(attrs={'class': 'control-panel', 'min': '1', 'placeholder': '7',
                                                      'data-duracion': ''}),
            'indicaciones': texto('Ej.: con comida'),
        }


class VacunaAplicadaForm(forms.ModelForm):
    """
    Una vacuna aplicada en la consulta. Solo se ofrecen las vacunas activas de la especie de la mascota
    (y la que ya tenía, si se está editando). La mascota y el veterinario los pone la vista antes de validar.
    """

    class Meta:
        model = VacunaAplicada
        fields = ['vacuna', 'lote']
        widgets = {
            'vacuna': forms.Select(attrs={'class': 'control-panel'}),
            'lote': texto('Ej.: L-2026-11'),
        }

    def __init__(self, *args, mascota, veterinario, fecha, **kwargs):
        super().__init__(*args, **kwargs)
        # Se ponen antes de validar: así clean() del modelo revisa que la vacuna sea de su especie
        self.instance.mascota = mascota
        self.instance.veterinario = veterinario
        if not self.instance.pk:
            self.instance.fecha_aplicacion = fecha
        disponibles = HistorialService.vacunas_para(mascota)
        self.fields['vacuna'].queryset = Vacuna.objects.filter(
            Q(pk__in=disponibles) | Q(pk=self.instance.vacuna_id)
        ).select_related('especie')
        self.fields['vacuna'].empty_label = 'Elige una vacuna'


# Una fila vacía para empezar; el botón "Agregar" (consulta.js) suma más. Las filas sin tocar se ignoran
RecetaFormSet = forms.inlineformset_factory(
    Consulta, Prescripcion, form=PrescripcionForm, extra=1, can_delete=True,
)
VacunasFormSet = forms.inlineformset_factory(
    Consulta, VacunaAplicada, form=VacunaAplicadaForm, fk_name='consulta', extra=1, can_delete=True,
)
