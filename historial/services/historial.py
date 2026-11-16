from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from citas.models import EstadoCita
from historial.models import Consulta, Vacuna, VacunaAplicada
from mascotas.models import Mascota


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

    @staticmethod
    def consulta_de(cita):
        """
        La consulta de la cita para el formulario: la que ya tiene (para editarla) o una nueva sin guardar,
        con la cita, la mascota, el veterinario, la fecha y el motivo de la reserva ya puestos.
        """
        consulta = Consulta.objects.filter(cita=cita).first()
        if consulta is None:
            consulta = Consulta(cita=cita, mascota=cita.mascota, veterinario=cita.veterinario, fecha=cita.inicio,
                                motivo=cita.motivo)
        return consulta

    @staticmethod
    def fecha_de_la_cita(cita):
        """El día de la cita (en la hora de Ecuador): la fecha de aplicación de sus vacunas."""
        return timezone.localtime(cita.inicio).date()

    @staticmethod
    def guardar_consulta(consulta_form, recetas, vacunas):
        """
        Guarda la consulta, su receta y sus vacunas como una sola operación: si algo falla, no queda nada a medias.
        Los formularios ya vienen validados por la vista. Si se escribió el peso, pasa a ser el peso de la mascota.
        """
        with transaction.atomic():
            consulta = consulta_form.save()
            recetas.instance = consulta
            recetas.save()
            vacunas.instance = consulta
            vacunas.save()
            if consulta.peso_kg:
                # update(): solo cambia el peso, sin pasar por el formulario de la mascota
                Mascota.objects.filter(pk=consulta.mascota_id).update(peso_kg=consulta.peso_kg)
        return consulta
