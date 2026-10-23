from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

from .models import Usuario


class RegistroForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'cedula']
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo',
            'telefono': 'Teléfono',
            'cedula': 'Cédula',
        }
        widgets = {
            # Solo cambian cómo se ve el campo: teclado numérico en el celular y como máximo 10 caracteres
            'cedula': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 10, 'placeholder': 'Tus 10 números'}),
        }


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label='Código', max_length=6, min_length=6, validators=[RegexValidator(r'^\d{6}$', 'Escribe los 6 números del código.')])
    

class UsuarioRolForm(forms.ModelForm):
    """Lo único que el administrador cambia de una cuenta desde el panel: su rol y si puede entrar."""

    class Meta:
        model = Usuario
        fields = ['rol', 'is_active']
        labels = {'rol': 'Rol', 'is_active': 'Cuenta activa'}
        help_texts = {'is_active': 'Si la desactivas, la persona ya no puede iniciar sesión. Sus datos se conservan.'}
