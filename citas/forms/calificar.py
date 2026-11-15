"""La calificación del cliente: de 1 a 5 estrellas y un comentario opcional."""
from django import forms

from ..services import TEXTO_ESTRELLAS


class CalificarCitaForm(forms.Form):
    """Solo valida la entrada; que la cita se pueda calificar lo decide AgendaService.calificar()."""
    estrellas = forms.TypedChoiceField(
        label='¿Cómo fue la atención?',
        choices=list(TEXTO_ESTRELLAS.items()),
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={'required': 'Elige de 1 a 5 estrellas.', 'invalid_choice': 'Elige de 1 a 5 estrellas.'},
    )
    comentario = forms.CharField(
        label='Comentario (opcional)',
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'control-panel',
                                     'placeholder': 'Cuéntanos qué te gustó o qué podría mejorar'}),
    )
