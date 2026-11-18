"""Las calificaciones de las citas: quién puede calificar y la reputación de cada veterinario (F7)."""
from django.db.models import Avg, Count, Q

from citas.models import ESTRELLAS_MAX, ESTRELLAS_MIN, Calificacion, EstadoCita

# Texto de cada cantidad de estrellas (el que se ve debajo de las estrellas al calificar)
TEXTO_ESTRELLAS = {1: 'Mala', 2: 'Regular', 3: 'Buena', 4: 'Muy buena', 5: 'Excelente'}


def _redondear(promedio):
    return round(promedio, 1) if promedio is not None else None


class CalificacionService:

    @staticmethod
    def puede_calificar(cita):
        """Solo una cita atendida que todavía no tiene calificación."""
        return cita.estado == EstadoCita.ATENDIDA and not Calificacion.objects.filter(cita=cita).exists()

    @staticmethod
    def del_veterinario(veterinario):
        return Calificacion.objects.filter(cita__veterinario=veterinario)

    @staticmethod
    def filtradas(veterinario=None, estrellas=None):
        """
        Las opiniones de la clínica, de la más nueva a la más vieja, con la cita, la mascota, el dueño, el
        servicio y el veterinario ya cargados. Se pueden dejar solo las de un veterinario o de N estrellas.
        """
        calificaciones = Calificacion.objects.select_related(
            'cita__mascota__dueno__ciudad', 'cita__servicio', 'cita__veterinario',
        ).defer('cita__mascota__foto')   # la foto se guarda en la base: no hace falta traer sus bytes
        if veterinario is not None:
            calificaciones = calificaciones.filter(cita__veterinario=veterinario)
        if estrellas:
            calificaciones = calificaciones.filter(estrellas=estrellas)
        return calificaciones

    @staticmethod
    def resumen(calificaciones, recientes=5):
        """
        La reputación de un grupo de opiniones: promedio (None si no hay ninguna), total, cuántas hay de
        cada cantidad de estrellas (de 5 a 1, con su porcentaje), cuántas traen comentario y las más recientes.
        """
        datos = calificaciones.aggregate(
            promedio=Avg('estrellas'), total=Count('pk'), con_comentario=Count('pk', filter=~Q(comentario='')),
        )
        total = datos['total']
        por_estrellas = dict(calificaciones.order_by().values_list('estrellas').annotate(cantidad=Count('pk')))
        distribucion = [
            {
                'estrellas': estrellas,
                'cantidad': por_estrellas.get(estrellas, 0),
                'porcentaje': round(por_estrellas.get(estrellas, 0) * 100 / total) if total else 0,
            }
            for estrellas in range(ESTRELLAS_MAX, ESTRELLAS_MIN - 1, -1)
        ]
        positivas = por_estrellas.get(4, 0) + por_estrellas.get(5, 0)
        return {
            'promedio': _redondear(datos['promedio']),
            'total': total,
            'con_comentario': datos['con_comentario'],
            # Opiniones de 4 o 5 estrellas sobre el total (None si nadie calificó)
            'satisfaccion': round(positivas * 100 / total) if total else None,
            'distribucion': distribucion,
            'recientes': list(
                calificaciones.select_related('cita__mascota__dueno', 'cita__servicio')[:recientes]
            ),
        }

    @staticmethod
    def resumen_del_veterinario(veterinario, recientes=5):
        """La reputación del veterinario (la del perfil, la de Calificar y la de Mis calificaciones)."""
        return CalificacionService.resumen(CalificacionService.del_veterinario(veterinario), recientes)

    @staticmethod
    def desempeno_por_veterinario(veterinarios):
        """
        Una fila por veterinario con su promedio, cuántas opiniones tiene, cuántas son de 4-5 y de 1-2
        estrellas. Primero los mejor calificados; los que nadie calificó van al final.
        """
        filas = veterinarios.annotate(
            promedio=Avg('citas_atendidas__calificacion__estrellas'),
            total=Count('citas_atendidas__calificacion'),
            positivas=Count('citas_atendidas__calificacion', filter=Q(citas_atendidas__calificacion__estrellas__gte=4)),
            negativas=Count('citas_atendidas__calificacion', filter=Q(citas_atendidas__calificacion__estrellas__lte=2)),
        )
        resultado = [
            {
                'veterinario': vet,
                'promedio': _redondear(vet.promedio),
                'total': vet.total,
                'positivas': vet.positivas,
                'negativas': vet.negativas,
                'porcentaje': round((vet.promedio or 0) * 100 / ESTRELLAS_MAX),   # para la barra
            }
            for vet in filas
        ]
        return sorted(resultado, key=lambda fila: (fila['promedio'] is None, -(fila['promedio'] or 0), -fila['total']))

    @staticmethod
    def promedio_dado_por(cliente):
        """El promedio de estrellas que el cliente ha dado (el indicador de Mis citas), o None."""
        promedio = Calificacion.objects.filter(cita__mascota__dueno=cliente).aggregate(promedio=Avg('estrellas'))
        return _redondear(promedio['promedio'])
