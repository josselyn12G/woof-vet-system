from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from cuentas.models import Roles

from .models import HorarioVeterinario, Servicio


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


class HorarioForm(forms.ModelForm):
    """Un bloque del horario. El veterinario no va en el formulario: la vista lo toma de request.user
    y lo pone en la instancia antes de validar, así clean() del modelo revisa los cruces con sus bloques."""

    class Meta:
        model = HorarioVeterinario
        fields = ['fecha', 'hora_inicio', 'hora_fin']
        widgets = {
            # format: el input type="date" y type="time" solo entienden 2026-11-02 y 09:00
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'control-panel'}, format='%Y-%m-%d'),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'control-panel'}, format='%H:%M'),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'step': 900, 'class': 'control-panel'}, format='%H:%M'),
        }

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('Ese día ya pasó: elige hoy o una fecha futura.')
        return fecha


class MisServiciosForm(forms.Form):
    """Los servicios que atiende el veterinario: casillas con los servicios activos del catálogo."""
    servicios = forms.ModelMultipleChoiceField(
        label='Servicios que atiendo',
        queryset=Servicio.objects.filter(activo=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
