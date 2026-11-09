"""Los filtros de la gestión de citas (administrador)."""
from django import forms

from ..models import EstadoCita
from ..services import CitaService, ServicioService
from .campos import VeterinarioOpcion


class FiltroCitasForm(forms.Form):
    """Filtros de la gestión de citas (administrador). Todos opcionales y por GET: un valor inventado
    en la URL no rompe la página, el campo queda sin filtrar."""
    q = forms.CharField(required=False, max_length=80)
    estado = forms.ChoiceField(required=False, choices=[('', 'Todos los estados')] + EstadoCita.choices)
    veterinario = VeterinarioOpcion(required=False, queryset=CitaService.veterinarios().none(),
                                    empty_label='Todos los veterinarios')
    servicio = forms.ModelChoiceField(required=False, queryset=ServicioService.todos(), empty_label='Todos los servicios')

    def __init__(self, *args, veterinarios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veterinario'].queryset = veterinarios
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'control-panel'
            if isinstance(campo.widget, forms.Select):
                # Como en los demás filtros del panel: elegir una opción ya filtra
                campo.widget.attrs.update({'class': 'control-panel filtros__rol', 'onchange': 'this.form.submit()'})

    def filtros(self):
        """Los filtros válidos; los que no pasan la validación se ignoran."""
        self.is_valid()
        datos = getattr(self, 'cleaned_data', {})
        return {
            'buscar': (datos.get('q') or '').strip(),
            'estado': datos.get('estado') or '',
            'veterinario': datos.get('veterinario'),
            'servicio': datos.get('servicio'),
        }
