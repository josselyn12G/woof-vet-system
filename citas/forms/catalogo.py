"""El formulario de un servicio del catálogo (administrador)."""
from django import forms

from ..models import Servicio
from ..services import CitaService, ServicioService
from .campos import VeterinarioCasillas


class ServicioForm(forms.ModelForm):
    # Solo veterinarios activos y verificados: un cliente, una cuenta desactivada o un veterinario sin verificar
    # no aparecen ni se aceptan
    veterinarios = VeterinarioCasillas(
        label='Veterinarios que lo atienden',
        queryset=CitaService.veterinarios(activos=True, verificados=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Servicio
        fields = ['nombre', 'descripcion', 'duracion_min', 'precio', 'veterinarios', 'activo']
        labels = {'activo': 'Servicio activo'}
        help_texts = {'activo': 'Si lo desactivas ya no se ofrece al agendar; las citas pasadas lo conservan.'}
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            # min y step solo ayudan en el navegador: la regla real (mayor que 0) la valida el modelo
            'duracion_min': forms.NumberInput(attrs={'min': 1, 'step': 5}),
            'precio': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
        }

    def clean_veterinarios(self):
        # Los que ya lo atendían pero no salen en las casillas (sin verificar o desactivados) se conservan:
        # guardar el servicio no debe quitárselo a nadie sin que el administrador lo vea
        elegidos = self.cleaned_data['veterinarios']
        if not self.instance.pk:
            return elegidos
        ocultos = self.instance.veterinarios.exclude(pk__in=self.fields['veterinarios'].queryset)
        return list(elegidos) + list(ocultos)

    def clean_nombre(self):
        # "Vacunación" y "vacunación" son el mismo servicio aunque la base los vea distintos
        nombre = ' '.join(self.cleaned_data['nombre'].split())
        if ServicioService.nombre_repetido(nombre, excluir_pk=self.instance.pk):
            raise forms.ValidationError('Ya existe un servicio con ese nombre.')
        return nombre
