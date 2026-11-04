from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Count, ExpressionWrapper, Q, Sum
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario
from citas.services.formato import minutos, texto_duracion
from cuentas.models import Roles

# Pestañas de Mis citas (cliente): valor en la URL (?vista=) -> nombre que se muestra
VISTAS_CITAS = {'proximas': 'Próximas', 'pasadas': 'Pasadas', 'canceladas': 'Canceladas'}
# Pestañas de la gestión de citas (administrador)
VISTAS_GESTION = {'proximas': 'Próximas', 'hoy': 'Hoy', 'pasadas': 'Pasadas', 'todas': 'Todas'}


def con_foto_de_la_mascota(citas):
    """Sin los bytes de la foto de la mascota, pero sabiendo si tiene una (para el avatar)."""
    citas = list(
        citas.defer('mascota__foto')
        .annotate(foto_mascota=ExpressionWrapper(Q(mascota__foto__isnull=False), output_field=BooleanField()))
    )
    for cita in citas:
        cita.mascota.tiene_foto = cita.foto_mascota
    return citas


class CitaService:
    """Consultas de citas para cada pantalla: Mis citas, la agenda del veterinario y la gestión de la clínica."""

    # ---------- Cliente ----------
    @staticmethod
    def del_cliente(cliente, vista='proximas'):
        """
        Las citas de las mascotas del cliente repartidas en próximas, pasadas y canceladas,
        con las de la pestaña elegida agrupadas por día: [(fecha, [citas]), ...].
        """
        ahora = timezone.now()
        citas = con_foto_de_la_mascota(
            Cita.objects.filter(mascota__dueno=cliente).select_related('mascota', 'servicio', 'veterinario')
        )
        proximas = [c for c in citas if c.estado == EstadoCita.CONFIRMADA and c.inicio > ahora]
        canceladas = sorted((c for c in citas if c.estado == EstadoCita.CANCELADA), key=lambda c: c.inicio, reverse=True)
        pasadas = sorted((c for c in citas if c not in proximas and c not in canceladas), key=lambda c: c.inicio, reverse=True)
        listas = {'proximas': proximas, 'pasadas': pasadas, 'canceladas': canceladas}

        por_dia = {}
        for cita in listas[vista]:
            por_dia.setdefault(timezone.localtime(cita.inicio).date(), []).append(cita)

        return {
            'pestanas': [(valor, nombre, len(listas[valor])) for valor, nombre in VISTAS_CITAS.items()],
            'por_dia': list(por_dia.items()),
            'proximas': proximas,
            'proxima': proximas[0] if proximas else None,
            'ultima': pasadas[0] if pasadas else None,
        }

    @staticmethod
    def proximas_del_cliente(cliente, cantidad=4):
        return list(
            Cita.objects.filter(mascota__dueno=cliente, estado=EstadoCita.CONFIRMADA, inicio__gt=timezone.now())
            .select_related('mascota', 'servicio', 'veterinario')[:cantidad]
        )

    # ---------- Veterinario ----------
    @staticmethod
    def agenda_del_dia(veterinario, fecha):
        """
        La agenda del veterinario ese día: sus citas en orden de hora (con la foto de la mascota, la duración
        y si ya se pueden cerrar), un resumen por estado, los bloques de su horario y la semana de ese día
        con cuántas citas tiene cada uno (para cambiar de día).
        """
        ahora = timezone.now()
        hoy = timezone.localdate()
        citas = con_foto_de_la_mascota(
            Cita.objects.filter(veterinario=veterinario, inicio__date=fecha)
            .select_related('mascota', 'mascota__dueno', 'servicio')
            .order_by('inicio')
        )
        for cita in citas:
            cita.duracion = texto_duracion(int((cita.fin - cita.inicio).total_seconds() // 60))
            # Confirmada y ya empezó: el veterinario la cierra como atendida o no asistió
            cita.puede_cerrarse = cita.estado == EstadoCita.CONFIRMADA and cita.inicio <= ahora

        bloques = list(HorarioVeterinario.objects.filter(veterinario=veterinario, fecha=fecha))
        for bloque in bloques:
            bloque.duracion = texto_duracion(minutos(bloque))

        # La semana de ese día (lunes a domingo) con las citas activas de cada día
        lunes = fecha - timedelta(days=fecha.weekday())
        por_dia = {}
        for inicio in (
            Cita.objects.filter(veterinario=veterinario, inicio__date__range=(lunes, lunes + timedelta(days=6)))
            .exclude(estado=EstadoCita.CANCELADA).values_list('inicio', flat=True)
        ):
            dia = timezone.localtime(inicio).date()
            por_dia[dia] = por_dia.get(dia, 0) + 1

        contar = {estado: sum(1 for cita in citas if cita.estado == estado) for estado in EstadoCita.values}
        activas = len(citas) - contar[EstadoCita.CANCELADA]
        # La línea de "ahora" va antes de la primera cita que todavía no empieza (solo si se mira hoy)
        indice_ahora = None
        if fecha == hoy and citas:
            indice_ahora = next((i for i, cita in enumerate(citas) if cita.inicio > ahora), len(citas))

        return {
            'citas': citas,
            'activas': activas,
            'resumen': {
                'por_atender': contar[EstadoCita.CONFIRMADA],
                'atendidas': contar[EstadoCita.ATENDIDA],
                'no_asistio': contar[EstadoCita.NO_ASISTIO],
                'canceladas': contar[EstadoCita.CANCELADA],
                # Cuánto del día ya se cerró (atendidas y no asistió sobre las citas activas)
                'avance': round((contar[EstadoCita.ATENDIDA] + contar[EstadoCita.NO_ASISTIO]) * 100 / activas)
                if activas else 0,
            },
            'indice_ahora': indice_ahora,
            'bloques': bloques,
            'total_horario': texto_duracion(sum(minutos(bloque) for bloque in bloques)) if bloques else '',
            'semana_agenda': [
                {'fecha': dia, 'citas': por_dia.get(dia, 0), 'es_hoy': dia == hoy, 'es_elegido': dia == fecha}
                for dia in (lunes + timedelta(days=i) for i in range(7))
            ],
        }

    # ---------- Administrador ----------
    @staticmethod
    def de_la_clinica(vista='proximas', buscar='', estado='', veterinario=None, servicio=None):
        """Todas las citas de la clínica con los filtros de la gestión (todos opcionales)."""
        ahora = timezone.now()
        citas = Cita.objects.select_related('mascota', 'mascota__dueno', 'servicio', 'veterinario')
        if vista == 'hoy':
            citas = citas.filter(inicio__date=timezone.localdate()).order_by('inicio')
        elif vista == 'proximas':
            citas = citas.filter(inicio__gt=ahora).order_by('inicio')
        elif vista == 'pasadas':
            citas = citas.filter(inicio__lte=ahora).order_by('-inicio')
        else:
            citas = citas.order_by('-inicio')

        if buscar:
            citas = citas.filter(
                Q(mascota__nombre__icontains=buscar)
                | Q(mascota__dueno__first_name__icontains=buscar) | Q(mascota__dueno__last_name__icontains=buscar)
                | Q(mascota__dueno__username__icontains=buscar) | Q(mascota__dueno__cedula__icontains=buscar)
                | Q(motivo__icontains=buscar)
            )
        if estado in EstadoCita.values:   # un estado inventado en la URL se ignora
            citas = citas.filter(estado=estado)
        if veterinario:
            citas = citas.filter(veterinario=veterinario)
        if servicio:
            citas = citas.filter(servicio=servicio)
        return citas

    @staticmethod
    def resumen_de_la_clinica():
        """Cifras de la gestión de citas: hoy, los próximos 7 días y lo que pasó en los últimos 30."""
        ahora = timezone.now()
        hoy = timezone.localdate()
        hace_un_mes = ahora - timedelta(days=30)
        activas = ~Q(estado=EstadoCita.CANCELADA)
        cuentas = Cita.objects.aggregate(
            hoy=Count('pk', filter=Q(inicio__date=hoy) & activas),
            semana=Count('pk', filter=Q(inicio__gt=ahora, inicio__lte=ahora + timedelta(days=7),
                                        estado=EstadoCita.CONFIRMADA)),
            atendidas=Count('pk', filter=Q(inicio__gte=hace_un_mes, estado=EstadoCita.ATENDIDA)),
            canceladas=Count('pk', filter=Q(inicio__gte=hace_un_mes, estado=EstadoCita.CANCELADA)),
            no_asistio=Count('pk', filter=Q(inicio__gte=hace_un_mes, estado=EstadoCita.NO_ASISTIO)),
            ingresos=Sum('precio', filter=Q(inicio__gte=hace_un_mes, estado=EstadoCita.ATENDIDA)),
        )
        cuentas['ingresos'] = cuentas['ingresos'] or 0
        return cuentas

    @staticmethod
    def veterinarios():
        """Los veterinarios para el filtro de la gestión (también los desactivados: sus citas siguen ahí)."""
        return get_user_model().objects.filter(rol=Roles.VETERINARIO).order_by('first_name', 'last_name', 'username')
