from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from .validators import validar_cedula

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
    SUPERADMIN = 'superadmin', 'Superadministrador'


# Roles que administran la clínica: el superadministrador puede todo lo que hace un administrador
ROLES_DE_GESTION = (Roles.ADMINISTRADOR, Roles.SUPERADMIN)
# Cuentas del personal (las que gestiona el superadministrador)
ROLES_DEL_PERSONAL = (Roles.VETERINARIO, Roles.ADMINISTRADOR, Roles.SUPERADMIN)


class UsuarioManager(UserManager):
    """createsuperuser crea un superadministrador de Woof (además de darle acceso a /admin/)."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('rol', Roles.SUPERADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    # Atributos del usuario
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=16, validators=[validar_telefono])
    rol = models.CharField(max_length=15, choices=Roles.choices, default=Roles.CLIENTE)
    sector = models.CharField(max_length=80, blank=True)  # opcional: se guarda '' si está vacío
    cedula = models.CharField(max_length=10, unique=True, validators=[validar_cedula])

    REQUIRED_FIELDS = ['email', 'telefono', 'cedula']

    objects = UsuarioManager()

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
            models.CheckConstraint(
                condition=models.Q(cedula__regex=r'^\d{10}$'),
                name='usuario_cedula_formato',
            ),
        ]

    # Funcion que devuelve el nombre completo o su nombre de usuario
    def __str__(self):
        return self.get_full_name() or self.get_username()

    @property
    def es_cliente(self):
        return self.rol == Roles.CLIENTE

    @property
    def es_veterinario(self):
        return self.rol == Roles.VETERINARIO

    @property
    def es_administrador(self):
        return self.rol == Roles.ADMINISTRADOR

    @property
    def es_superadmin(self):
        return self.rol == Roles.SUPERADMIN

    @property
    def gestiona_clinica(self):
        """True para el administrador y el superadministrador: los dos ven el panel de la clínica."""
        return self.rol in ROLES_DE_GESTION
