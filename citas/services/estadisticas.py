from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario
from citas.services.formato import minutos


def porcentaje(parte, total):
    """Con un decimal, como el ejemplo del documento (80 ÷ 240 = 33,3 %); 0 si no hay total."""
    return round(parte * 100 / total, 1) if total else 0


class EstadisticasService:
    """Cifras de la portada del veterinario y de los indicadores de la clínica, a partir de las citas y los horarios."""

    @staticmethod
    def indicadores(desde, hasta, veterinario=None):
        """
        Indicadores de la agenda entre dos fechas (RF-25, §2.5), de toda la clínica o de un veterinario:

        - citas por estado (las canceladas también, para saber cuántas hubo);
        - por veterinario: sus citas, la ocupación = Σ minutos de citas no canceladas ÷ Σ minutos de sus bloques × 100
          y los ingresos (precio copiado de las citas atendidas);
        - los totales de la clínica con la misma fórmula.
        """
        citas = Cita.objects.filter(inicio__date__range=(desde, hasta))
        bloques = HorarioVeterinario.objects.filter(fecha__range=(desde, hasta))
        if veterinario is not None:
            citas = citas.filter(veterinario=veterinario)
            bloques = bloques.filter(veterinario=veterinario)
        citas = list(citas.values_list('veterinario_id', 'estado', 'inicio', 'fin', 'precio'))
        bloques = list(bloques)

        # Un renglón por veterinario con citas o con horario en el período
        ids = {cita[0] for cita in citas} | {bloque.veterinario_id for bloque in bloques}
        filas = []
        for vet in get_user_model().objects.filter(pk__in=ids).order_by('first_name', 'last_name', 'username'):
            suyas = [cita for cita in citas if cita[0] == vet.pk]
            activas = [cita for cita in suyas if cita[1] != EstadoCita.CANCELADA]
            minutos_citas = sum((fin - inicio).total_seconds() / 60 for _, _, inicio, fin, _ in activas)
            minutos_horario = sum(minutos(bloque) for bloque in bloques if bloque.veterinario_id == vet.pk)
            filas.append({
                'veterinario': vet,
                'citas': len(activas),
                'atendidas': sum(1 for cita in suyas if cita[1] == EstadoCita.ATENDIDA),
                'no_asistio': sum(1 for cita in suyas if cita[1] == EstadoCita.NO_ASISTIO),
                'canceladas': len(suyas) - len(activas),
                'minutos_citas': minutos_citas,
                'minutos_horario': minutos_horario,
                'ocupacion': porcentaje(minutos_citas, minutos_horario),
                # El ancho de la barra: hasta 100 aunque alguna cita haya quedado fuera del horario
                'barra': min(porcentaje(minutos_citas, minutos_horario), 100),
                'ingresos': sum(precio for _, estado, _, _, precio in suyas if estado == EstadoCita.ATENDIDA),
            })

        minutos_citas = sum(fila['minutos_citas'] for fila in filas)
        minutos_horario = sum(fila['minutos_horario'] for fila in filas)
        return {
            'por_estado': [
                (valor, nombre, sum(1 for cita in citas if cita[1] == valor)) for valor, nombre in EstadoCita.choices
            ],
            'total_citas': len(citas),
            'filas': filas,
            'ocupacion': porcentaje(minutos_citas, minutos_horario),
            'ingresos': sum(fila['ingresos'] for fila in filas),
            'horas_horario': round(minutos_horario / 60, 1),
        }

    @staticmethod
    def del_veterinario(veterinario, desde, hasta):
        """
        Cifras de las citas del veterinario entre dos fechas y las del período anterior del mismo largo.

        Las canceladas no cuentan: no ocuparon tiempo. Devuelve las fechas y las citas por día
        (para el gráfico), las cifras del período ('actual') y las del anterior, para comparar.
        """
        dias = (hasta - desde).days + 1
        desde_anterior = desde - timedelta(days=dias)
        mis_citas = Cita.objects.filter(veterinario=veterinario).exclude(estado=EstadoCita.CANCELADA)
        del_periodo = mis_citas.filter(inicio__date__range=(desde, hasta))
        del_anterior = mis_citas.filter(inicio__date__range=(desde_anterior, desde - timedelta(days=1)))

        # Citas por día para el gráfico
        fechas = [desde + timedelta(days=i) for i in range(dias)]
        por_dia = {fecha: 0 for fecha in fechas}
        for inicio in del_periodo.values_list('inicio', flat=True):
            por_dia[timezone.localtime(inicio).date()] += 1
        citas_por_dia = [por_dia[fecha] for fecha in fechas]

        # Ocupación: minutos con cita sobre los minutos de horario publicado en el período
        minutos_citas = sum((fin - inicio).total_seconds() / 60 for inicio, fin in del_periodo.values_list('inicio', 'fin'))
        minutos_horario = sum(
            (datetime.combine(hasta, fin) - datetime.combine(hasta, inicio)).total_seconds() / 60
            for inicio, fin in HorarioVeterinario.objects
            .filter(veterinario=veterinario, fecha__range=(desde, hasta))
            .values_list('hora_inicio', 'hora_fin')
        )

        def contar(consulta, estado=None):
            return consulta.filter(estado=estado).count() if estado else consulta.count()

        return {
            'fechas': fechas,
            'citas_por_dia': citas_por_dia,
            'actual': {
                'citas': sum(citas_por_dia),
                'atendidas': contar(del_periodo, EstadoCita.ATENDIDA),
                'ocupacion': round(minutos_citas * 100 / minutos_horario) if minutos_horario else 0,
                'no_asistio': contar(del_periodo, EstadoCita.NO_ASISTIO),
                # suma del precio copiado en las citas atendidas del período
                'ganancias': del_periodo.filter(estado=EstadoCita.ATENDIDA).aggregate(total=Sum('precio'))['total'] or 0,
            },
            'anterior': {
                'citas': contar(del_anterior),
                'atendidas': contar(del_anterior, EstadoCita.ATENDIDA),
                'no_asistio': contar(del_anterior, EstadoCita.NO_ASISTIO),
            },
        }
