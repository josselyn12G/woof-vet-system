"""Gestión de cuentas: el rol que da el administrador y el equipo del superadministrador."""
from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from ..models import Roles, Usuario
from ..services import PoliticaDeCuentas
from .comunes import CEDULA, ETIQUETAS, con_estilo_del_panel


class RolSegunQuienEditaMixin:
    """El desplegable de rol solo ofrece lo que quien edita puede dar (PoliticaDeCuentas), y nadie
    se quita su propio rol ni desactiva su cuenta."""

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        persona = self.instance if self.instance.pk else None
        self.fields['rol'].choices = PoliticaDeCuentas.roles_asignables(actor, persona)

    def clean(self):
        datos = super().clean()
        if self.instance.pk and 'rol' in datos:
            activo = datos.get('is_active', self.instance.is_active)
            try:
                PoliticaDeCuentas.validar_cambio(self.actor, self.instance, datos['rol'], activo)
            except forms.ValidationError as error:
                self.add_error(None, error)
        return datos


class UsuarioRolForm(RolSegunQuienEditaMixin, forms.ModelForm):
    """Lo único que el administrador cambia de una cuenta desde el panel: su rol y si puede entrar."""

    class Meta:
        model = Usuario
        fields = ['rol', 'is_active']
        labels = {'rol': 'Rol', 'is_active': 'Cuenta activa'}
        help_texts = {'is_active': 'Si la desactivas, la persona ya no puede iniciar sesión. Sus datos se conservan.'}


class PersonalCreacionForm(RolSegunQuienEditaMixin, UserCreationForm):
    """El superadministrador crea la cuenta de un veterinario o de un administrador, con su contraseña inicial."""

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'telefono', 'cedula', 'rol']
        labels = {campo: ETIQUETAS[campo] for campo in fields}
        widgets = {'cedula': CEDULA, 'telefono': forms.TextInput(attrs={'placeholder': '+593987654321'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Una cuenta nueva del personal es de veterinario o de administrador (no de cliente)
        self.fields['rol'].choices = [(valor, nombre) for valor, nombre in self.fields['rol'].choices
                                      if valor in (Roles.VETERINARIO, Roles.ADMINISTRADOR)]
        self.fields['rol'].initial = Roles.VETERINARIO
        for campo in ('first_name', 'last_name'):
            self.fields[campo].required = True
        # UserCreationForm enfoca el usuario; aquí el primer campo es el nombre
        self.fields['username'].widget.attrs.pop('autofocus', None)
        self.fields['first_name'].widget.attrs['autofocus'] = True
        self.fields['password1'].label = 'Contraseña inicial'
        self.fields['password2'].label = 'Repite la contraseña'
        con_estilo_del_panel(self)


class PersonalForm(RolSegunQuienEditaMixin, forms.ModelForm):
    """El superadministrador corrige los datos de una persona del equipo, su rol y si puede entrar."""

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'cedula', 'sector', 'rol', 'is_active']
        labels = {campo: ETIQUETAS[campo] for campo in fields}
        help_texts = {'is_active': 'Si la desactivas, la persona ya no puede iniciar sesión. Sus datos se conservan.'}
        widgets = {'cedula': CEDULA}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ('first_name', 'last_name'):
            self.fields[campo].required = True
        con_estilo_del_panel(self)


class NuevaContrasenaForm(SetPasswordForm):
    """El superadministrador le pone una contraseña nueva a una persona del equipo (por ejemplo, si la olvidó)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Contraseña nueva'
        self.fields['new_password2'].label = 'Repite la contraseña'
        con_estilo_del_panel(self)
