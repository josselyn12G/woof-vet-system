from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario


class EstadisticasService:
    """Cifras de la portada del veterinario, calculadas a partir de sus citas y su horario."""

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
