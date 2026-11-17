"""Una vacuna del catálogo (administrador): nombre, especie, cada cuánto se refuerza y si se ofrece."""
from django import forms

from cuentas.forms import con_estilo_del_panel
from mascotas.forms.comunes import sin_espacios_de_mas

from ..models import Vacuna
from ..services import VacunaCatalogoService


class VacunaForm(forms.ModelForm):
    """No se repite el nombre en la misma especie: "Rabia" puede estar para perro y para gato."""

    class Meta:
        model = Vacuna
        fields = ['nombre', 'especie', 'refuerzo_cada_dias', 'activa']
        labels = {'nombre': 'Nombre', 'especie': 'Especie', 'refuerzo_cada_dias': 'Refuerzo cada (días)',
                  'activa': 'Vacuna activa'}
        help_texts = {
            'especie': 'Déjala en "Todas las especies" si sirve para cualquier mascota.',
            'refuerzo_cada_dias': 'Vacío si no lleva refuerzo. Con él, la próxima dosis se calcula sola (365 = un año).',
            'activa': 'Si la desactivas ya no se ofrece al registrar una consulta; los carnets la siguen mostrando.',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej.: Rabia'}),
            'refuerzo_cada_dias': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Ej.: 365'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['especie'].queryset = VacunaCatalogoService.especies_para_elegir(self.instance.especie_id)
        self.fields['especie'].empty_label = 'Todas las especies'
        con_estilo_del_panel(self)

    def clean_nombre(self):
        return sin_espacios_de_mas(self.cleaned_data['nombre'])

    def clean(self):
        datos = super().clean()
        nombre, especie = datos.get('nombre'), datos.get('especie')
        if nombre and VacunaCatalogoService.nombre_repetido(nombre, especie, self.instance.pk):
            para = f'para {especie}' if especie else 'para todas las especies'
            self.add_error('nombre', f'Ya existe la vacuna {nombre} {para}.')
        return datos
