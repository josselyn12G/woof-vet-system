from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario

TURNO_OCUPADO = 'Ese horario ya no está disponible. Elige otra hora.'


class AgendaService:
    """
    Reglas del Core: qué turnos están libres, cómo se agenda y cómo se cancela una cita.

    Las vistas solo llaman a estos métodos; así la lógica del negocio vive en un solo lugar
    y se puede probar sin pasar por formularios ni plantillas.
    """

    @staticmethod
    def espacios_disponibles(veterinario, servicio, fecha, excluir=None):
        """
        Devuelve las horas de inicio libres del veterinario para ese servicio en esa fecha.

        Corta cada bloque de su horario en turnos del largo del servicio y quita
        los que ya pasaron o se cruzan con una cita activa. Al reprogramar, excluir es la cita
        que se va a mover: su turno actual no cuenta como ocupado.
        """
        duracion = timedelta(minutes=servicio.duracion_min)
        zona = timezone.get_current_timezone()
        ahora = timezone.now()

        # Citas que ocupan tiempo ese día: todas menos las canceladas (y la que se reprograma)
        citas = Cita.objects.filter(veterinario=veterinario, inicio__date=fecha).exclude(estado=EstadoCita.CANCELADA)
        if excluir is not None:
            citas = citas.exclude(pk=excluir.pk)
        ocupadas = list(citas.values_list('inicio', 'fin'))

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
    def dias_disponibles(veterinario, servicio, anio, mes, excluir=None):
        """
        Devuelve los días del mes en que el veterinario tiene al menos un turno libre para el servicio.

        Solo revisa los días en que publicó horario (desde hoy); el calendario marca esos días.
        """
        fechas = sorted(set(
            HorarioVeterinario.objects
            .filter(veterinario=veterinario, fecha__year=anio, fecha__month=mes, fecha__gte=timezone.localdate())
            .values_list('fecha', flat=True)
        ))
        return [fecha for fecha in fechas if AgendaService.espacios_disponibles(veterinario, servicio, fecha, excluir)]

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
    def se_puede_reprogramar(cita):
        """Solo una cita confirmada que todavía no empieza (igual que para cancelarla)."""
        return cita.estado == EstadoCita.CONFIRMADA and cita.inicio > timezone.now()

    @staticmethod
    def dias_para_reprogramar(cita, anio, mes):
        """Días del mes con algún turno libre para la cita, con su mismo veterinario y servicio."""
        return AgendaService.dias_disponibles(cita.veterinario, cita.servicio, anio, mes, excluir=cita)

    @staticmethod
    def horas_para_reprogramar(cita, fecha):
        """Horas libres de ese día para mover la cita (sin su hora actual: moverla ahí no cambia nada)."""
        espacios = AgendaService.espacios_disponibles(cita.veterinario, cita.servicio, fecha, excluir=cita)
        return [inicio for inicio in espacios if inicio != cita.inicio]

    @staticmethod
    def reprogramar(cita, nuevo_inicio):
        """
        Mueve una cita confirmada a otro día u hora, con el mismo veterinario y el mismo servicio.

        Es una sola operación: dentro de una transacción, con el veterinario y la cita bloqueados, se revisa
        el turno nuevo y se actualizan el inicio y el fin de la MISMA fila (no se cancela una y se crea otra).
        Si algo falla, la transacción se deshace y la cita sigue en su hora de antes: nunca se pierde la reserva.
        """
        if nuevo_inicio <= timezone.now():
            raise ValidationError('Elige una hora que todavía no haya pasado.')

        with transaction.atomic():
            # Primero el veterinario, como en agendar(): nadie más reserva con él hasta que esto termine.
            # Después la propia cita: otra pestaña no puede cancelarla ni moverla al mismo tiempo
            get_user_model().objects.select_for_update().get(pk=cita.veterinario_id)
            cita = Cita.objects.select_for_update().select_related('servicio', 'veterinario').get(pk=cita.pk)

            # Las reglas se revisan con la cita ya bloqueada (pudo cambiar desde que se abrió la página)
            if not AgendaService.se_puede_reprogramar(cita):
                raise ValidationError('Solo se puede reprogramar una cita confirmada que todavía no empieza.')
            if nuevo_inicio == cita.inicio:
                raise ValidationError('Esa ya es la hora de la cita. Elige otra.')
            if not cita.servicio.activo:
                raise ValidationError('Ese servicio ya no se ofrece.')
            if not cita.servicio.veterinarios.filter(pk=cita.veterinario_id).exists():
                raise ValidationError('El veterinario ya no atiende este servicio.')

            fecha = timezone.localtime(nuevo_inicio).date()
            if nuevo_inicio not in AgendaService.espacios_disponibles(cita.veterinario, cita.servicio, fecha,
                                                                       excluir=cita):
                raise ValidationError(TURNO_OCUPADO)

            # La misma fila: cambia la hora, se conservan la mascota, el veterinario, el precio y el motivo
            cita.inicio = nuevo_inicio
            cita.fin = nuevo_inicio + timedelta(minutes=cita.servicio.duracion_min)
            try:
                cita.save(update_fields=['inicio', 'fin'])
            except IntegrityError:
                # La UniqueConstraint atrapó un choque que se coló: ROLLBACK, la cita queda en su hora anterior
                raise ValidationError(TURNO_OCUPADO)
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
