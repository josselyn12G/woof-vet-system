"""Las calificaciones de las citas: quién puede calificar y la reputación de cada veterinario (F7)."""
from django.db.models import Avg, Count

from citas.models import ESTRELLAS_MAX, ESTRELLAS_MIN, Calificacion, EstadoCita

# Texto de cada cantidad de estrellas (el que se ve debajo de las estrellas al calificar)
TEXTO_ESTRELLAS = {1: 'Mala', 2: 'Regular', 3: 'Buena', 4: 'Muy buena', 5: 'Excelente'}


class CalificacionService:

    @staticmethod
    def puede_calificar(cita):
        """Solo una cita atendida que todavía no tiene calificación."""
        return cita.estado == EstadoCita.ATENDIDA and not Calificacion.objects.filter(cita=cita).exists()

    @staticmethod
    def del_veterinario(veterinario):
        return Calificacion.objects.filter(cita__veterinario=veterinario)

    @staticmethod
    def resumen_del_veterinario(veterinario, recientes=5):
        """
        La reputación del veterinario: promedio (None si nadie lo calificó), total de opiniones,
        cuántas hay de cada cantidad de estrellas (de 5 a 1, con su porcentaje) y las más recientes.
        """
        calificaciones = CalificacionService.del_veterinario(veterinario)
        datos = calificaciones.aggregate(promedio=Avg('estrellas'), total=Count('pk'))
        total = datos['total']
        por_estrellas = dict(calificaciones.values_list('estrellas').annotate(cantidad=Count('pk')))
        distribucion = [
            {
                'estrellas': estrellas,
                'cantidad': por_estrellas.get(estrellas, 0),
                'porcentaje': round(por_estrellas.get(estrellas, 0) * 100 / total) if total else 0,
            }
            for estrellas in range(ESTRELLAS_MAX, ESTRELLAS_MIN - 1, -1)
        ]
        return {
            'promedio': round(datos['promedio'], 1) if datos['promedio'] is not None else None,
            'total': total,
            'distribucion': distribucion,
            'recientes': list(
                calificaciones.select_related('cita__mascota__dueno', 'cita__servicio')[:recientes]
            ),
        }

    @staticmethod
    def promedio_dado_por(cliente):
        """El promedio de estrellas que el cliente ha dado (el indicador de Mis citas), o None."""
        promedio = Calificacion.objects.filter(cita__mascota__dueno=cliente).aggregate(promedio=Avg('estrellas'))
        return round(promedio['promedio'], 1) if promedio['promedio'] is not None else None
