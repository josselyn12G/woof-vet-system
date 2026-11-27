"""
El carnet de vacunación de cada mascota: el estado de cada vacuna (al día, próxima, vencida, reforzada) y las
vacunas que se le pueden aplicar. Salió de HistorialService (principio de responsabilidad única).
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from historial.models import Vacuna, VacunaAplicada

# Una vacuna cuya próxima dosis cae dentro de estos días aparece como «próxima» en el carnet
DIAS_PARA_PROXIMA = 30

# Estado de cada línea del carnet: (clave para el CSS, texto que se muestra)
AL_DIA = ('al_dia', 'Al día')
PROXIMA = ('proxima', 'Próxima')
VENCIDA = ('vencida', 'Vencida')
REFORZADA = ('reforzada', 'Reforzada')


class CarnetService:
    """El carnet de vacunación: lo usan la historia clínica, el carnet 3D de Mis mascotas y la consulta."""

    @staticmethod
    def estado_de_la_vacuna(proxima_dosis, hoy=None):
        """
        «Vencida» si la próxima dosis ya pasó, «próxima» si falta menos de 30 días y «al día» en otro caso
        (también si la vacuna no lleva refuerzo).
        """
        hoy = hoy or timezone.localdate()
        if proxima_dosis is None:
            return AL_DIA
        if proxima_dosis < hoy:
            return VENCIDA
        if proxima_dosis - hoy < timedelta(days=DIAS_PARA_PROXIMA):
            return PROXIMA
        return AL_DIA

    @staticmethod
    def carnet(mascota, hoy=None):
        """
        Las líneas del carnet de vacunación (HU-36), de la más reciente a la más antigua: vacuna, fecha, lote,
        veterinario, próxima dosis y estado. También salen las vacunas que ya se desactivaron del catálogo.

        Solo la última dosis de cada vacuna lleva estado; las anteriores quedan como «reforzada»,
        así una dosis vieja ya renovada no aparece como vencida.
        """
        lineas = list(
            VacunaAplicada.objects.filter(mascota=mascota).select_related('vacuna', 'veterinario')
        )
        ya_vistas = set()
        for aplicada in lineas:   # vienen de la más nueva a la más vieja (ordering del modelo)
            if aplicada.vacuna_id in ya_vistas:
                aplicada.estado, aplicada.estado_texto = REFORZADA
            else:
                aplicada.estado, aplicada.estado_texto = CarnetService.estado_de_la_vacuna(
                    aplicada.proxima_dosis, hoy,
                )
                ya_vistas.add(aplicada.vacuna_id)
        return lineas

    @staticmethod
    def carnet_en_datos(lineas):
        """Las líneas del carnet como datos simples, para que el librito 3D (carnet-3d.js) las dibuje."""
        return [
            {
                'vacuna': aplicada.vacuna.nombre,
                'fecha': aplicada.fecha_aplicacion.strftime('%d/%m/%Y'),
                'lote': aplicada.lote or '—',
                'proxima': aplicada.proxima_dosis.strftime('%d/%m/%Y') if aplicada.proxima_dosis else '—',
                'veterinario': aplicada.veterinario.nombre_completo,
                'estado': aplicada.estado,
                'estado_texto': aplicada.estado_texto,
            }
            for aplicada in lineas
        ]

    @staticmethod
    def vacunas_para(mascota):
        """Las vacunas activas que se le pueden aplicar: las de su especie y las que sirven para todas."""
        return Vacuna.objects.filter(Q(especie__isnull=True) | Q(especie=mascota.especie_id), activa=True)

    @staticmethod
    def vacunas_para_elegir(mascota, actual_pk=None):
        """Las del desplegable al registrar una vacuna: las que se le pueden aplicar y, al editar, la que ya tiene."""
        return Vacuna.objects.filter(
            Q(pk__in=CarnetService.vacunas_para(mascota)) | Q(pk=actual_pk)
        ).select_related('especie')
