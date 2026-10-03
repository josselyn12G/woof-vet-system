from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

# Formato E.164 (+ y de 8 a 15 dígitos): es el que exige Twilio para enviar el SMS.
validar_telefono = RegexValidator(
    regex=r'^\+\d{8,15}$',
    message='Ingresa el número en formato internacional, por ejemplo +593987654321.',
)


class Usuario(AbstractUser):
    """Usuario de Woof: el de Django (username, password, nombre...) más teléfono, rol y sector."""

    class Rol(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        VETERINARIO = 'veterinario', 'Veterinario'
        ADMIN = 'admin', 'Administrador'

    # AbstractUser ya trae email, pero permite repetirlo; aquí lo hacemos único.
    email = models.EmailField('correo electrónico', unique=True)
    telefono = models.CharField(
        'teléfono celular',
        max_length=16,
        validators=[validar_telefono],
        help_text='Formato internacional, por ejemplo +593987654321. Aquí llega el código de verificación.',
    )
    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.CLIENTE)
    sector = models.CharField(max_length=80, blank=True)

    # Campos que pide `createsuperuser` además del username y la contraseña.
    REQUIRED_FIELDS = ['email', 'telefono']

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return self.get_full_name() or self.username
