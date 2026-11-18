"""Mi horario: un bloque de horario y los servicios que atiende el veterinario."""
from django import forms
from django.utils import timezone

from ..models import HorarioVeterinario
from ..services import HorarioService, ServicioService
from .campos import SelectorHora


class HorarioForm(forms.ModelForm):
    """Un bloque del horario. El veterinario no va en el formulario: la vista lo toma de request.user
    y lo pone en la instancia antes de validar, así clean() del modelo revisa los cruces con sus bloques."""

    class Meta:
        model = HorarioVeterinario
        fields = ['fecha', 'hora_inicio', 'hora_fin']
        widgets = {
            # format: el input type="date" y type="time" solo entienden 2026-11-02 y 09:00
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'control-panel', 'data-fecha-bloque': ''},
                                     format='%Y-%m-%d'),
            'hora_inicio': SelectorHora(),
            'hora_fin': SelectorHora(),
        }

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('Ese día ya pasó: elige hoy o una fecha futura.')
        return fecha

    def clean(self):
        datos = super().clean()
        # Al editar, self.instance todavía tiene el bloque guardado (los datos nuevos se copian después):
        # se revisa que sus citas confirmadas sigan cabiendo en el día y las horas nuevas (RF-09)
        nuevos = [datos.get(campo) for campo in ('fecha', 'hora_inicio', 'hora_fin')]
        if self.instance.pk and all(nuevos):
            HorarioService.validar_cambio(self.instance, *nuevos)
        return datos


class MisServiciosForm(forms.Form):
    """Los servicios que atiende el veterinario: casillas con los servicios activos del catálogo."""
    servicios = forms.ModelMultipleChoiceField(
        label='Servicios que atiendo',
        queryset=ServicioService.activos(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
