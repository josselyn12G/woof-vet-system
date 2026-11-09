from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from cuentas.models import ROLES_DEL_PERSONAL, Roles

# El superadministrador da cualquier rol; el administrador solo maneja clientes y veterinarios
ROLES_QUE_ASIGNA = {
    Roles.SUPERADMIN: tuple(Roles.values),
    Roles.ADMINISTRADOR: (Roles.CLIENTE, Roles.VETERINARIO),
}
ESTADOS_CUENTA = {'activas': True, 'desactivadas': False}


class PoliticaDeCuentas:
    """
    Quién gestiona qué cuenta. Está en un solo lugar para que el formulario, las vistas y las plantillas
    apliquen la misma regla:
    - El superadministrador gestiona a todos (también a los administradores y a otros superadministradores).
    - El administrador gestiona clientes y veterinarios, y abre su propia cuenta; no toca a otros administradores.
    - Nadie se quita su propio rol ni desactiva su propia cuenta: se quedaría sin acceso al panel.
    """

    @staticmethod
    def roles_asignables(actor, persona=None):
        """Los roles que el actor puede dar, como (valor, nombre). Su propia cuenta conserva el rol que tiene."""
        valores = set(ROLES_QUE_ASIGNA.get(actor.rol, ()))
        if persona is not None:
            valores.add(persona.rol)   # el rol actual siempre se puede dejar como está
        return [(valor, nombre) for valor, nombre in Roles.choices if valor in valores]

    @staticmethod
    def puede_gestionar(actor, persona):
        if actor.es_superadmin:
            return True
        if actor.es_administrador:
            return persona.pk == actor.pk or persona.rol in ROLES_QUE_ASIGNA[Roles.ADMINISTRADOR]
        return False

    @staticmethod
    def exigir_gestion(actor, persona):
        """Lanza PermissionDenied (Django responde 403) si actor no puede gestionar esa cuenta."""
        if not PoliticaDeCuentas.puede_gestionar(actor, persona):
            raise PermissionDenied

    @staticmethod
    def destino_permitido(usuario, url):
        """
        A dónde ir después del login. Si la página guardada en ?next= es de otro rol (por ejemplo,
        "Mis mascotas" del cliente cuando entra un veterinario), se va a /panel/, que lleva a la de su rol.
        """
        try:
            vista = resolve(urlsplit(url).path).func
        except Resolver404:
            return url
        roles = getattr(getattr(vista, 'view_class', None), 'roles_permitidos', None)
        if roles and usuario.rol not in roles:
            return reverse('panel:panel')
        return url

    @staticmethod
    def validar_cambio(actor, persona, rol, activo):
        if persona.pk == actor.pk and (rol != actor.rol or not activo):
            raise ValidationError(
                f'No puedes quitarte el rol de {actor.get_rol_display().lower()} ni desactivar tu propia cuenta.'
            )


def filtro_de_busqueda(texto):
    return (
        Q(username__icontains=texto) | Q(first_name__icontains=texto) | Q(last_name__icontains=texto)
        | Q(email__icontains=texto) | Q(cedula__icontains=texto)
    )


class UsuarioService:
    """Consultas y cambios de cuentas para el panel del administrador y del superadministrador."""

    @staticmethod
    def todas():
        """Todas las cuentas: las vistas buscan aquí la de la URL (404 si no está)."""
        return get_user_model().objects.all()

    @staticmethod
    def buscar(texto='', rol=''):
        usuarios = get_user_model().objects.order_by('-date_joined')
        if texto:
            usuarios = usuarios.filter(filtro_de_busqueda(texto))
        if rol in Roles.values:  # un rol inventado en la URL se ignora
            usuarios = usuarios.filter(rol=rol)
        return usuarios

    @staticmethod
    def personal(texto='', rol='', estado=''):
        """El equipo de la clínica (veterinarios, administradores y superadministradores)."""
        personas = get_user_model().objects.filter(rol__in=ROLES_DEL_PERSONAL).order_by('rol', 'first_name', 'last_name')
        if texto:
            personas = personas.filter(filtro_de_busqueda(texto))
        if rol in ROLES_DEL_PERSONAL:
            personas = personas.filter(rol=rol)
        if estado in ESTADOS_CUENTA:
            personas = personas.filter(is_active=ESTADOS_CUENTA[estado])
        return personas

    @staticmethod
    def marcar_gestionables(actor, personas):
        """Agrega persona.gestionable a cada cuenta: la plantilla muestra "Editar" solo en esas."""
        for persona in personas:
            persona.gestionable = PoliticaDeCuentas.puede_gestionar(actor, persona)
        return personas

    @staticmethod
    def alternar_activa(actor, persona):
        """Activa o desactiva la cuenta y devuelve cómo quedó. Nadie se desactiva a sí mismo."""
        PoliticaDeCuentas.validar_cambio(actor, persona, persona.rol, not persona.is_active)
        persona.is_active = not persona.is_active
        persona.save(update_fields=['is_active'])
        return persona.is_active

    @staticmethod
    def filas_del_reporte():
        """Las cuentas para el CSV, sin contraseñas."""
        yield ['Usuario', 'Nombre', 'Correo', 'Rol', 'Cédula', 'Teléfono', 'Activa', 'Registro']
        for persona in get_user_model().objects.order_by('date_joined'):
            yield [
                persona.username, persona.get_full_name(), persona.email, persona.get_rol_display(),
                persona.cedula, persona.telefono, 'Sí' if persona.is_active else 'No',
                timezone.localtime(persona.date_joined).strftime('%Y-%m-%d %H:%M'),
            ]
