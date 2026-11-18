"""El perfil del veterinario que edita el administrador: especialidad, experiencia y verificación."""
from django import forms

from ..models import PerfilVeterinario
from .comunes import con_estilo_del_panel


class PerfilVeterinarioForm(forms.ModelForm):
    class Meta:
        model = PerfilVeterinario
        fields = ['especialidad', 'anios_experiencia', 'descripcion', 'verificado']
        labels = {'verificado': 'Veterinario verificado'}
        help_texts = {
            'verificado': 'Solo los veterinarios verificados se ofrecen al agendar y en el catálogo de servicios.',
        }
        widgets = {
            'especialidad': forms.TextInput(attrs={'placeholder': 'Por ejemplo, Medicina general'}),
            'anios_experiencia': forms.NumberInput(attrs={'min': 0}),
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('prefix', 'perfil')   # convive en la misma página con el formulario de la cuenta
        super().__init__(*args, **kwargs)
        con_estilo_del_panel(self)
