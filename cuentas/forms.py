from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

from .models import Usuario


class RegistroForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono']
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo',
            'telefono': 'Teléfono',
        }


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label='Código', max_length=6, min_length=6, validators=[RegexValidator(r'^\d{6}$', 'Escribe los 6 números del código.')])
    