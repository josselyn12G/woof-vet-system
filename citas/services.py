from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
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


class HorarioService:
    """
    Reglas del horario del veterinario: copiar una semana y elegir los servicios que atiende.

    Las vistas solo reciben el pedido y muestran el mensaje; qué se guarda se decide aquí.
    """

    @staticmethod
    def copiar_semana(veterinario, lunes):
        """
        Copia los bloques de la semana anterior en la semana que empieza en ese lunes.

        Se saltan los días que ya pasaron y los bloques que se cruzarían con otros ya cargados.
        Devuelve (copiados, omitidos), o lanza ValidationError si la semana anterior no tiene bloques.
        """
        hoy = timezone.localdate()
        propios = HorarioVeterinario.objects.filter(veterinario=veterinario)
        anteriores = propios.filter(fecha__range=(lunes - timedelta(days=7), lunes - timedelta(days=1)))
        if not anteriores:
            raise ValidationError('La semana anterior no tiene bloques para copiar.')

        copiados = omitidos = 0
        for bloque in anteriores:
            nuevo = HorarioVeterinario(veterinario=veterinario, fecha=bloque.fecha + timedelta(days=7),
                                       hora_inicio=bloque.hora_inicio, hora_fin=bloque.hora_fin)
            # Misma regla de cruce que HorarioVeterinario.clean(): empieza antes de que el otro termine y al revés
            cruza = propios.filter(fecha=nuevo.fecha, hora_inicio__lt=nuevo.hora_fin,
                                   hora_fin__gt=nuevo.hora_inicio).exists()
            if nuevo.fecha < hoy or cruza:
                omitidos += 1
                continue
            nuevo.save()
            copiados += 1
        return copiados, omitidos

    @staticmethod
    def guardar_servicios(veterinario, servicios):
        """
        Deja como servicios del veterinario los elegidos, más los desactivados que ya atendía.

        Los inactivos no se muestran como casillas, así que no se pueden desmarcar: se conservan.
        """
        inactivos = list(veterinario.servicios.filter(activo=False))
        veterinario.servicios.set(list(servicios) + inactivos)


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
                'ganancias': del_periodo.filter(estado=EstadoCita.ATENDIDA).aggregate(total=models.Sum('precio'))['total'] or 0,
            },
            'anterior': {
                'citas': contar(del_anterior),
                'atendidas': contar(del_anterior, EstadoCita.ATENDIDA),
                'no_asistio': contar(del_anterior, EstadoCita.NO_ASISTIO),
            },
        }
