from django import forms
from django.contrib.auth import get_user_model

from cuentas.models import Roles

from .models import Servicio


class VeterinarioCasillas(forms.ModelMultipleChoiceField):
    """Cada veterinario es una casilla con su nombre (nunca un input donde se escribe el id)."""

    def label_from_instance(self, veterinario):
        return veterinario.get_full_name() or veterinario.username


class ServicioForm(forms.ModelForm):
    # Solo veterinarios con la cuenta activa: un cliente o una cuenta desactivada no aparecen ni se aceptan
    veterinarios = VeterinarioCasillas(
        label='Veterinarios que lo atienden',
        queryset=get_user_model().objects.filter(rol=Roles.VETERINARIO, is_active=True).order_by('first_name', 'last_name'),
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

    def clean_nombre(self):
        # "Vacunación" y "vacunación" son el mismo servicio aunque la base los vea distintos
        nombre = ' '.join(self.cleaned_data['nombre'].split())
        repetido = Servicio.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError('Ya existe un servicio con ese nombre.')
        return nombre
