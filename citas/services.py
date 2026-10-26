from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Cita, EstadoCita, HorarioVeterinario

TURNO_OCUPADO = 'Ese horario ya no está disponible. Elige otra hora.'


class AgendaService:
    """
    Reglas del Core: qué turnos están libres, cómo se agenda y cómo se cancela una cita.

    Las vistas solo llaman a estos métodos; así la lógica del negocio vive en un solo lugar
    y se puede probar sin pasar por formularios ni plantillas.
    """

    @staticmethod
    def espacios_disponibles(veterinario, servicio, fecha):
        """
        Devuelve las horas de inicio libres del veterinario para ese servicio en esa fecha.

        Corta cada bloque de su horario en turnos del largo del servicio y quita
        los que ya pasaron o se cruzan con una cita activa.
        """
        duracion = timedelta(minutes=servicio.duracion_min)
        zona = timezone.get_current_timezone()
        ahora = timezone.now()

        # Citas que ocupan tiempo ese día: todas menos las canceladas
        ocupadas = list(
            Cita.objects
            .filter(veterinario=veterinario, inicio__date=fecha)
            .exclude(estado=EstadoCita.CANCELADA)
            .values_list('inicio', 'fin')
        )

        espacios = []
        for bloque in HorarioVeterinario.objects.filter(veterinario=veterinario, fecha=fecha):
            inicio = timezone.make_aware(datetime.combine(fecha, bloque.hora_inicio), zona)
            limite = timezone.make_aware(datetime.combine(fecha, bloque.hora_fin), zona)
            # El turno debe caber completo dentro del bloque
            while inicio + duracion <= limite:
                fin = inicio + duracion
                # Dos turnos se cruzan si uno empieza antes de que el otro termine (igual que en el horario)
                cruzado = any(otra_inicio < fin and otra_fin > inicio for otra_inicio, otra_fin in ocupadas)
                if inicio > ahora and not cruzado:
                    espacios.append(inicio)
                inicio = fin
        return espacios

    @staticmethod
    def dias_disponibles(veterinario, servicio, anio, mes):
        """
        Devuelve los días del mes en que el veterinario tiene al menos un turno libre para el servicio.

        Solo revisa los días en que publicó horario (desde hoy); el calendario marca esos días.
        """
        fechas = sorted(set(
            HorarioVeterinario.objects
            .filter(veterinario=veterinario, fecha__year=anio, fecha__month=mes, fecha__gte=timezone.localdate())
            .values_list('fecha', flat=True)
        ))
        return [fecha for fecha in fechas if AgendaService.espacios_disponibles(veterinario, servicio, fecha)]

    @staticmethod
    def dias_del_servicio(servicio, anio, mes):
        """Días del mes en que algún veterinario del servicio tiene un turno libre (el calendario los resalta)."""
        dias = set()
        for veterinario in servicio.veterinarios.filter(is_active=True):
            dias.update(AgendaService.dias_disponibles(veterinario, servicio, anio, mes))
        return sorted(dias)

    @staticmethod
    def turnos_del_dia(servicio, fecha):
        """
        Las horas libres de ese día agrupadas por veterinario: [(veterinario, [inicio, ...]), ...].

        Así el cliente elige la hora y, con ella, el doctor que lo atiende.
        """
        turnos = []
        for veterinario in servicio.veterinarios.filter(is_active=True).order_by('first_name', 'last_name'):
            espacios = AgendaService.espacios_disponibles(veterinario, servicio, fecha)
            if espacios:
                turnos.append((veterinario, espacios))
        return turnos

    @staticmethod
    def agendar(mascota, veterinario, servicio, inicio, motivo=''):
        """
        Crea la cita ya confirmada, o lanza ValidationError si el turno no es válido.

        Todo pasa en una transacción con la fila del veterinario bloqueada: si dos clientes
        piden el mismo turno a la vez, el segundo espera y luego ve que ya no está libre.
        """
        if not servicio.activo:
            raise ValidationError('Ese servicio ya no se ofrece.')
        if not servicio.veterinarios.filter(pk=veterinario.pk).exists():
            raise ValidationError('Ese veterinario no atiende este servicio.')
        if inicio <= timezone.now():
            raise ValidationError('Elige una hora que todavía no haya pasado.')

        with transaction.atomic():
            # select_for_update: nadie más agenda con este veterinario hasta que termine la transacción
            get_user_model().objects.select_for_update().get(pk=veterinario.pk)

            fecha = timezone.localtime(inicio).date()
            if inicio not in AgendaService.espacios_disponibles(veterinario, servicio, fecha):
                raise ValidationError(TURNO_OCUPADO)

            try:
                return Cita.objects.create(
                    mascota=mascota,
                    veterinario=veterinario,
                    servicio=servicio,
                    inicio=inicio,
                    fin=inicio + timedelta(minutes=servicio.duracion_min),
                    precio=servicio.precio,   # copia: si el servicio cambia de precio, esta cita no cambia
                    motivo=motivo,
                )
            except IntegrityError:
                # La UniqueConstraint de la base atrapó un choque que se coló: se avisa igual que arriba
                raise ValidationError(TURNO_OCUPADO)

    @staticmethod
    def cancelar(cita):
        """
        Cancela una cita confirmada que todavía no empieza; su turno vuelve a quedar libre.

        Una cita atendida, no asistida o ya cancelada no se puede cancelar.
        """
        if cita.estado != EstadoCita.CONFIRMADA:
            raise ValidationError('Solo se puede cancelar una cita confirmada.')
        if cita.inicio <= timezone.now():
            raise ValidationError('La cita ya empezó; no se puede cancelar.')

        cita.estado = EstadoCita.CANCELADA
        cita.save(update_fields=['estado'])
        return cita

    @staticmethod
    def registrar_resultado(cita, estado):
        """
        El veterinario cierra la cita como atendida o no asistió.

        Solo se cierra una cita confirmada que ya empezó: antes de su hora no se sabe si la mascota llegó.
        """
        if estado not in (EstadoCita.ATENDIDA, EstadoCita.NO_ASISTIO):
            raise ValidationError('Ese resultado no es válido.')
        if cita.estado != EstadoCita.CONFIRMADA:
            raise ValidationError('Esta cita ya fue cerrada o cancelada.')
        if cita.inicio > timezone.now():
            raise ValidationError('La cita todavía no empieza.')

        cita.estado = estado
        cita.save(update_fields=['estado'])
        return cita
