"""Entrar a Woof: el registro, el código de 6 dígitos del login en dos pasos y recuperar la contraseña."""
from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils import timezone

from ..models import Usuario
from ..services.correo import enviar_correo_con_enlace
from ..services.ubicacion import UbicacionService
from .comunes import ETIQUETAS
from .ubicacion import UbicacionMixin


class RegistroForm(UbicacionMixin, UserCreationForm):
    """
    El registro del cliente (HU-01). País → provincia → ciudad son desplegables dependientes (UbicacionMixin);
    la casilla de los términos es obligatoria y se guarda cuándo se aceptaron (HU-23).
    """
    acepto_terminos = forms.BooleanField(
        label='Acepto los términos de uso y la política de tratamiento de datos',
        error_messages={'required': 'Para crear la cuenta tienes que aceptar los términos y la política de datos.'},
    )

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'cedula', 'ciudad']
        labels = {campo: ETIQUETAS[campo] for campo in fields}
        widgets = {
            'cedula': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 10, 'placeholder': 'Tus 10 números'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Al abrir, Ecuador queda elegido y la provincia se elige de sus 24
        self.preparar_ubicacion(pais=getattr(UbicacionService.pais_por_defecto(), 'pk', None))

    def clean(self):
        datos = super().clean()
        self.validar_ubicacion(datos)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.terminos_aceptados_en = timezone.now()   # HU-23: queda constancia de cuándo aceptó
        if commit:
            usuario.save()
        return usuario


class RecuperarContrasenaForm(PasswordResetForm):
    """HU-14: el correo con el enlace para crear una contraseña nueva, con el mismo diseño que los demás de Woof."""

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        enlace = f"{context['protocol']}://{context['domain']}" + reverse(
            'cuentas:contrasena_nueva', args=[context['uid'], context['token']],
        )
        enviar_correo_con_enlace(
            context['user'],
            asunto='Crea una contraseña nueva en Woof',
            titulo='Crea una contraseña nueva',
            texto='Pediste crear una contraseña nueva para tu cuenta de Woof. Toca el botón para elegirla.',
            boton='Crear contraseña nueva',
            enlace=enlace,
            aviso='El enlace sirve una sola vez y vence en 3 días. Si no lo pediste, ignora este correo: '
                  'tu contraseña sigue igual.',
        )


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label='Código', max_length=6, min_length=6, validators=[RegexValidator(r'^\d{6}$', 'Escribe los 6 números del código.')])
