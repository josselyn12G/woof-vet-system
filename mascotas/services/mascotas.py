from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from cuentas.models import Roles
from mascotas.models import Especie, Mascota


def filtro_de_busqueda(texto):
    """Busca por el nombre de la mascota o por nombre, usuario, correo, cédula o teléfono del dueño."""
    return (
        Q(nombre__icontains=texto)
        | Q(dueno__first_name__icontains=texto) | Q(dueno__last_name__icontains=texto)
        | Q(dueno__username__icontains=texto) | Q(dueno__email__icontains=texto)
        | Q(dueno__cedula__icontains=texto) | Q(dueno__telefono__icontains=texto)
    )


class MascotaService:
    """
    Consultas de mascotas: las vistas piden los datos aquí y solo se ocupan de la petición y la plantilla.
    """

    @staticmethod
    def del_dueno(dueno):
        """Solo las mascotas de esa persona: la de otro cliente no está en la consulta (404 en el detalle)."""
        return Mascota.objects.del_dueno(dueno).con_foto()

    @staticmethod
    def nombre_repetido(dueno, nombre, excluir_pk=None):
        """True si ese dueño ya tiene otra mascota con ese nombre (sin importar mayúsculas)."""
        return Mascota.objects.filter(dueno=dueno, nombre__iexact=nombre).exclude(pk=excluir_pk).exists()

    @staticmethod
    def duenos_posibles(actual_pk=None):
        """Las cuentas de cliente, que pueden ser dueñas de una mascota; al editar, también el dueño que ya tiene."""
        duenos = Q(rol=Roles.CLIENTE)
        if actual_pk:
            duenos |= Q(pk=actual_pk)
        return get_user_model().objects.filter(duenos).order_by('first_name', 'last_name', 'username')

    @staticmethod
    def nombre_guardado(pk):
        """El nombre que está en la base (el formulario con errores trae el que se escribió)."""
        return Mascota.objects.values_list('nombre', flat=True).get(pk=pk)

    @staticmethod
    def pacientes(veterinario, buscar='', solo_mios=False):
        """Mascotas de los clientes con su dueño y cuántas citas tuvieron con este veterinario."""
        mascotas = (
            Mascota.objects.filter(dueno__rol=Roles.CLIENTE)
            .select_related('dueno')
            .con_foto()
            .annotate(citas_conmigo=Count('citas', filter=Q(citas__veterinario=veterinario)))
            .order_by('nombre')
        )
        if buscar:
            mascotas = mascotas.filter(filtro_de_busqueda(buscar))
        if solo_mios:
            mascotas = mascotas.filter(citas_conmigo__gt=0)
        return mascotas

    @staticmethod
    def de_la_clinica(buscar='', especie=''):
        """Todas las mascotas registradas, para el administrador: con su dueño y cuántas citas tienen.
        especie es el código (?especie=gato); uno inventado en la URL no filtra nada."""
        mascotas = (
            Mascota.objects.select_related('dueno')
            .con_foto()
            .annotate(total_citas=Count('citas'))
            .order_by('nombre')
        )
        if buscar:
            mascotas = mascotas.filter(filtro_de_busqueda(buscar))
        if especie and Especie.objects.filter(codigo=especie).exists():
            mascotas = mascotas.filter(especie__codigo=especie)
        return mascotas

    @staticmethod
    def resumen_de_la_clinica():
        """
        Cifras de la gestión de mascotas: total, registradas en los últimos 30 días y por especie.
        por_especie son las especies que tienen mascotas (para los filtros); en las cifras, perros y gatos
        van aparte y el resto se suma en "Otras especies".
        """
        hace_un_mes = timezone.now() - timedelta(days=30)
        cuentas = Mascota.objects.aggregate(total=Count('pk'), nuevas=Count('pk', filter=Q(creado__gte=hace_un_mes)))
        por_especie = [
            {'codigo': especie.codigo, 'nombre': especie.nombre, 'plural': especie.plural, 'estilo': especie.estilo,
             'cantidad': especie.cantidad}
            for especie in Especie.objects.annotate(cantidad=Count('mascotas')).filter(cantidad__gt=0)
        ]
        principales = [fila for fila in por_especie if fila['codigo'] in ('perro', 'gato')]
        otras = sum(fila['cantidad'] for fila in por_especie if fila not in principales)
        cifras = principales + ([{'plural': 'Otras especies', 'estilo': 'otro', 'cantidad': otras}] if otras else [])
        return {
            'total': cuentas['total'],
            'nuevas': cuentas['nuevas'],
            'por_especie': por_especie,
            'cifras_especie': cifras,
        }

    @staticmethod
    def fichas():
        """Todas las mascotas con su dueño, sin los bytes de la foto (para la gestión de la clínica)."""
        return Mascota.objects.select_related('dueno').con_foto()

    @staticmethod
    def ficha_de_la_clinica(pk):
        """Una mascota cualquiera con su dueño (el administrador ve todas). Mascota.DoesNotExist si no existe."""
        return MascotaService.fichas().get(pk=pk)

    @staticmethod
    def total_citas(mascota):
        return mascota.citas.count()

    @staticmethod
    def citas_de(mascota):
        """El historial de citas de la mascota, de la más reciente a la más antigua."""
        return mascota.citas.select_related('servicio', 'veterinario').order_by('-inicio')
