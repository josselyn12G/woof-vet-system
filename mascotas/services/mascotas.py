from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from cuentas.models import Roles
from mascotas.models import Especies, Mascota


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
        """Todas las mascotas registradas, para el administrador: con su dueño y cuántas citas tienen."""
        mascotas = (
            Mascota.objects.select_related('dueno')
            .con_foto()
            .annotate(total_citas=Count('citas'))
            .order_by('nombre')
        )
        if buscar:
            mascotas = mascotas.filter(filtro_de_busqueda(buscar))
        if especie in Especies.values:   # una especie inventada en la URL se ignora
            mascotas = mascotas.filter(especie=especie)
        return mascotas

    @staticmethod
    def resumen_de_la_clinica():
        """Cifras de la gestión de mascotas: total, por especie y registradas en los últimos 30 días."""
        hace_un_mes = timezone.now() - timedelta(days=30)
        cuentas = Mascota.objects.aggregate(
            total=Count('pk'),
            nuevas=Count('pk', filter=Q(creado__gte=hace_un_mes)),
            **{valor: Count('pk', filter=Q(especie=valor)) for valor in Especies.values},
        )
        return {
            'total': cuentas['total'],
            'nuevas': cuentas['nuevas'],
            'por_especie': [(valor, nombre, cuentas[valor]) for valor, nombre in Especies.choices],
        }

    @staticmethod
    def ficha_de_la_clinica(pk):
        """Una mascota cualquiera con su dueño (el administrador ve todas). Mascota.DoesNotExist si no existe."""
        return Mascota.objects.select_related('dueno').con_foto().get(pk=pk)

    @staticmethod
    def citas_de(mascota):
        """El historial de citas de la mascota, de la más reciente a la más antigua."""
        return mascota.citas.select_related('servicio', 'veterinario').order_by('-inicio')
