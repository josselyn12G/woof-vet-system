"""Campos y widgets que comparten varios formularios de citas."""
from django import forms


class VeterinarioCasillas(forms.ModelMultipleChoiceField):
    """Cada veterinario es una casilla con su nombre (nunca un input donde se escribe el id)."""

    def label_from_instance(self, veterinario):
        return veterinario.get_full_name() or veterinario.username


class VeterinarioOpcion(forms.ModelChoiceField):
    """En el desplegable se ve el nombre del veterinario, no su usuario."""

    def label_from_instance(self, veterinario):
        return veterinario.get_full_name() or veterinario.username


class SelectorHora(forms.TimeInput):
    """Hora cada 15 minutos. Sin JavaScript es el input type="time" del navegador; selector-hora.js
    (data-selector-hora) lo cambia por un botón que abre una grilla de horas y minutos."""
    input_type = 'time'

    def __init__(self, attrs=None):
        super().__init__(
            attrs={'step': 900, 'class': 'control-panel', 'data-selector-hora': '', **(attrs or {})},
            format='%H:%M',
        )
