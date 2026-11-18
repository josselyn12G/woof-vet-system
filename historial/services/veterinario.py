"""
Las dos páginas clínicas del veterinario (menú lateral): Consultas médicas y Vacunación.
Cada una trae cuatro cifras arriba y sus listas; todo se calcula aquí para que las vistas solo lo pasen.
"""
from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from citas.models import Cita, EstadoCita
from cuentas.models import Roles
from historial.models import Consulta, Prescripcion, VacunaAplicada

DIAS_PARA_REFUERZO = 30   # "Próximos refuerzos": los que tocan en los próximos 30 días


class ClinicaDelVeterinarioService:

    @staticmethod
    def consultas(veterinario, hoy=None):
        """
        Consultas médicas: las citas que ya atendió y todavía no tienen consulta (para registrarla) y sus
        últimas consultas registradas. Cifras del mes: consultas, por registrar, recetas y pacientes.
        """
        hoy = hoy or timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        con_consulta = Consulta.objects.filter(cita=OuterRef('pk'))
        por_registrar = list(
            Cita.objects.filter(veterinario=veterinario, estado=EstadoCita.ATENDIDA)
            .annotate(tiene_consulta=Exists(con_consulta)).filter(tiene_consulta=False)
            .select_related('mascota', 'servicio').order_by('-inicio')[:20]
        )
        registradas = list(
            Consulta.objects.filter(veterinario=veterinario)
            .select_related('mascota__especie', 'cita__servicio')
            .prefetch_related('prescripciones', 'vacunas_aplicadas')
            .order_by('-fecha')[:30]
        )
        del_mes = Consulta.objects.filter(veterinario=veterinario, fecha__date__gte=inicio_mes)
        return {
            'por_registrar': por_registrar,
            'registradas': registradas,
            'cifras': {
                'consultas_mes': del_mes.count(),
                'por_registrar': len(por_registrar),
                'recetas_mes': Prescripcion.objects.filter(consulta__in=del_mes).count(),
                'pacientes_mes': del_mes.values('mascota').distinct().count(),
            },
        }

    @staticmethod
    def vacunacion(veterinario, hoy=None):
        """
        Vacunación: las vacunas que aplicó y los refuerzos de los pacientes (la última dosis de cada vacuna):
        vencidos y los que tocan en los próximos 30 días. Cifras: aplicadas en el mes, próximos, vencidos y
        pacientes que vacunó.
        """
        hoy = hoy or timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        # La última dosis de cada vacuna por mascota: si hay una aplicación más nueva, esta ya no cuenta
        mas_nueva = VacunaAplicada.objects.filter(
            mascota=OuterRef('mascota'), vacuna=OuterRef('vacuna'), fecha_aplicacion__gt=OuterRef('fecha_aplicacion'),
        )
        refuerzos = (
            VacunaAplicada.objects.filter(proxima_dosis__isnull=False, proxima_dosis__lte=hoy + timedelta(days=DIAS_PARA_REFUERZO),
                                          mascota__dueno__rol=Roles.CLIENTE)
            .annotate(reemplazada=Exists(mas_nueva)).filter(reemplazada=False)
            .select_related('mascota__dueno', 'mascota__especie', 'vacuna').order_by('proxima_dosis')
        )
        vencidos = [r for r in refuerzos if r.proxima_dosis < hoy]
        proximos = [r for r in refuerzos if r.proxima_dosis >= hoy]
        for refuerzo in proximos:
            refuerzo.faltan = (refuerzo.proxima_dosis - hoy).days
        for refuerzo in vencidos:
            refuerzo.hace = (hoy - refuerzo.proxima_dosis).days
        aplicadas = list(
            VacunaAplicada.objects.filter(veterinario=veterinario)
            .select_related('mascota__especie', 'vacuna').order_by('-fecha_aplicacion', '-pk')[:30]
        )
        return {
            'aplicadas': aplicadas,
            'proximos': proximos,
            'vencidos': vencidos,
            'cifras': {
                'aplicadas_mes': VacunaAplicada.objects.filter(veterinario=veterinario, fecha_aplicacion__gte=inicio_mes).count(),
                'proximos': len(proximos),
                'vencidos': len(vencidos),
                'pacientes': VacunaAplicada.objects.filter(veterinario=veterinario).values('mascota').distinct().count(),
            },
        }
