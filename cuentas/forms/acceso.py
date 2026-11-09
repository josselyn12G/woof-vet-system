"""Entrar a Woof: el registro y el código de 6 dígitos del login en dos pasos."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

from ..models import Usuario
from .comunes import ETIQUETAS


class RegistroForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'cedula']
        labels = {campo: ETIQUETAS[campo] for campo in fields}
        widgets = {
            'cedula': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 10, 'placeholder': 'Tus 10 números'}),
        }


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label='Código', max_length=6, min_length=6, validators=[RegexValidator(r'^\d{6}$', 'Escribe los 6 números del código.')])
