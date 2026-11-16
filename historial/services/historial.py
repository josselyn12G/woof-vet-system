from django.db.models import Prefetch, Q

from citas.models import EstadoCita
from historial.models import Consulta, Vacuna, VacunaAplicada


class HistorialService:
    """
    La historia clínica de cada mascota: sus consultas (con receta) y sus vacunas.

    Las vistas del veterinario (registrar consulta), del cliente y del administrador (ver la historia)
    y el carnet de vacunación leen de aquí, así la consulta a la base vive en un solo lugar.
    """

    @staticmethod
    def de_la_mascota(mascota):
        """
        Las consultas de la mascota de la más nueva a la más vieja, cada una con su receta y sus vacunas,
        y todas sus vacunas aplicadas (también las cargadas sin consulta), para la línea de tiempo y el carnet.
        """
        vacunas = VacunaAplicada.objects.select_related('vacuna', 'veterinario')
        consultas = (
            Consulta.objects.filter(mascota=mascota)
            .select_related('veterinario', 'cita__servicio')
            .prefetch_related('prescripciones', Prefetch('vacunas_aplicadas', queryset=vacunas))
        )
        return {
            'consultas': list(consultas),
            'vacunas': list(vacunas.filter(mascota=mascota)),
        }

    @staticmethod
    def vacunas_para(mascota):
        """Las vacunas activas que se le pueden aplicar: las de su especie y las que sirven para todas."""
        return Vacuna.objects.filter(Q(especie__isnull=True) | Q(especie=mascota.especie_id), activa=True)

    @staticmethod
    def puede_registrar_consulta(cita):
        """Solo una cita atendida que todavía no tiene consulta (RF-20)."""
        return cita.estado == EstadoCita.ATENDIDA and not Consulta.objects.filter(cita=cita).exists()
