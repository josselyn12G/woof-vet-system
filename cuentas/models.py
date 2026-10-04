from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

# Validador del formato del telefono
validar_telefono = RegexValidator(
    regex=r'^\+\d{8,15}$',
    message='Ingresa el número en formato internacional, por ejemplo +593987654321.',
)


# Opciones fijas para los roles ya definidos
class Roles(models.TextChoices):
    CLIENTE = 'cliente', 'Cliente'
    VETERINARIO = 'veterinario', 'Veterinario'
    ADMINISTRADOR = 'administrador', 'Administrador'


class Usuario(AbstractUser):
    # Atributos del usuario
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=16, validators=[validar_telefono])
    rol = models.CharField(max_length=15, choices=Roles.choices, default=Roles.CLIENTE)
    sector = models.CharField(max_length=80, blank=True)  # opcional: se guarda '' si está vacío

    REQUIRED_FIELDS = ['email', 'telefono']

    # Clase que aporta metadatos al modelo
    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rol__in=Roles.values),
                name='usuario_rol_valido',
            ),
            models.CheckConstraint(
                condition=models.Q(telefono__regex=validar_telefono.regex.pattern),
                name='usuario_telefono_formato',
            ),
        ]

    # Funcion que devuelve el nombre completo o su nombre de usuario
    def __str__(self):
        return self.get_full_name() or self.get_username()
