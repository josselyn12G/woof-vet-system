from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario
from citas.services.consultas import con_foto_de_la_mascota
from citas.services.formato import minutos, texto_duracion
from cuentas.models import Roles

# La grilla de la semana va de 07:00 a 19:00, o más si algún bloque empieza antes o termina después
HORA_INICIO_GRILLA = 7
HORA_FIN_GRILLA = 19


def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def semana_pedida(texto):
    """El lunes de la semana que llega por ?semana=2026-11-04 (cualquier día sirve). Sin fecha o con
    una fecha inventada, la semana actual."""
    try:
        return lunes_de(date.fromisoformat(texto or ''))
    except ValueError:
        return lunes_de(timezone.localdate())


def leer_fecha(texto):
    """"2026-11-03" -> date; None si viene vacía o inventada."""
    try:
        return date.fromisoformat(texto or '')
    except ValueError:
        return None


def rango_de_horas(tramos):
    """Primera y última hora de la grilla: de 07 a 19, estirada para que entre cada tramo (inicio, fin)."""
    inicio = min([HORA_INICIO_GRILLA] + [desde.hour for desde, _ in tramos])
    fin = max([HORA_FIN_GRILLA] + [hasta.hour + (1 if hasta.minute else 0) for _, hasta in tramos])
    return inicio, fin


class HorarioService:
    """Mi horario (HU-26, RF-07 a RF-10) y los horarios de toda la clínica para el administrador."""

    @staticmethod
    def del_veterinario(veterinario):
        return HorarioVeterinario.objects.filter(veterinario=veterinario)

    @staticmethod
    def fecha_guardada(bloque):
        """La fecha que está en la base (el formulario con errores trae la que se escribió)."""
        return HorarioVeterinario.objects.values_list('fecha', flat=True).get(pk=bloque.pk)

    @staticmethod
    def citas_dentro(bloque):
        """Las citas confirmadas del veterinario que caen dentro del bloque: ese día, desde su hora de
        inicio y hasta su hora de fin. Las atendidas, no asistió y canceladas no cuentan (RF-09)."""
        return Cita.objects.filter(
            veterinario_id=bloque.veterinario_id, estado=EstadoCita.CONFIRMADA, inicio__date=bloque.fecha,
            inicio__time__gte=bloque.hora_inicio, fin__time__lte=bloque.hora_fin,
        )

    @staticmethod
    def aviso_citas_dentro(cantidad):
        """"Este bloque tiene 2 citas confirmadas. Reprográmalas o cancélalas primero." """
        confirmadas = 'cita confirmada' if cantidad == 1 else 'citas confirmadas'
        pronombre = 'la' if cantidad == 1 else 'las'
        return (f'Este bloque tiene {cantidad} {confirmadas}. '
                f'Reprográma{pronombre} o cancéla{pronombre} primero.')

    @staticmethod
    def validar_cambio(bloque, fecha, hora_inicio, hora_fin):
        """Al editar (recortar o mover) un bloque guardado: si alguna de sus citas confirmadas queda fuera
        del nuevo día u horario, no se permite el cambio (RF-09). Ampliar el bloque sí se puede."""
        fuera = 0
        for cita in HorarioService.citas_dentro(bloque):
            inicio, fin = timezone.localtime(cita.inicio), timezone.localtime(cita.fin)
            if not (inicio.date() == fecha and inicio.time() >= hora_inicio and fin.time() <= hora_fin):
                fuera += 1
        if fuera:
            raise ValidationError(HorarioService.aviso_citas_fuera(fuera))

    @staticmethod
    def aviso_citas_fuera(cantidad):
        """"Con este cambio, 2 citas confirmadas quedarían fuera del bloque. Reprográmalas o cancélalas primero." """
        confirmadas = '1 cita confirmada quedaría' if cantidad == 1 else f'{cantidad} citas confirmadas quedarían'
        pronombre = 'la' if cantidad == 1 else 'las'
        return (f'Con este cambio, {confirmadas} fuera del bloque. '
                f'Reprográma{pronombre} o cancéla{pronombre} primero.')

    @staticmethod
    def quitar_bloque(bloque):
        """Borra el bloque y devuelve su fecha (para volver a esa semana). Si tiene citas confirmadas no se
        borra: quedarían fuera del horario (RF-09)."""
        cantidad = HorarioService.citas_dentro(bloque).count()
        if cantidad:
            raise ValidationError(HorarioService.aviso_citas_dentro(cantidad))
        fecha = bloque.fecha
        bloque.delete()
        return fecha

    @staticmethod
    def servicios_activos(veterinario):
        """Los servicios activos que atiende: las casillas marcadas de "Servicios que atiendo"."""
        return veterinario.servicios.filter(activo=True)

    @staticmethod
    def semana_del_veterinario(veterinario, lunes):
        """
        La semana como columnas de días para la grilla: cada bloque trae su posición (arriba y alto, en %)
        dentro del rango de horas, su duración y cuántas citas activas tiene. Cada día trae también
        sus citas activas, ubicadas igual, con la mascota, su dueño y el servicio (para el detalle).
        """
        hoy = timezone.localdate()
        domingo = lunes + timedelta(days=6)
        bloques = list(HorarioService.del_veterinario(veterinario).filter(fecha__range=(lunes, domingo)))
        citas = con_foto_de_la_mascota(
            Cita.objects.filter(veterinario=veterinario, inicio__date__range=(lunes, domingo))
            .exclude(estado=EstadoCita.CANCELADA)
            .select_related('mascota', 'mascota__dueno', 'servicio')
            .order_by('inicio')
        )
        for cita in citas:
            cita.desde, cita.hasta = timezone.localtime(cita.inicio), timezone.localtime(cita.fin)

        hora_inicio, hora_fin = rango_de_horas(
            [(b.hora_inicio, b.hora_fin) for b in bloques] + [(c.desde.time(), c.hasta.time()) for c in citas]
        )
        largo = (hora_fin - hora_inicio) * 60

        def posicion(hora):
            return (hora.hour * 60 + hora.minute - hora_inicio * 60) * 100 / largo

        for cita in citas:
            cita.arriba = round(posicion(cita.desde), 3)
            cita.alto = round(posicion(cita.hasta) - posicion(cita.desde), 3)
            cita.minutos = int((cita.fin - cita.inicio).total_seconds() // 60)
            cita.duracion = texto_duracion(cita.minutos)

        for bloque in bloques:
            bloque.arriba = round(posicion(bloque.hora_inicio), 3)
            bloque.alto = round(posicion(bloque.hora_fin) - posicion(bloque.hora_inicio), 3)
            bloque.minutos = minutos(bloque)
            bloque.duracion = texto_duracion(bloque.minutos)
            # Citas que caen dentro del bloque: ese día y entre su hora de inicio y de fin
            bloque.citas = sum(
                1 for cita in citas
                if cita.desde.date() == bloque.fecha and cita.desde.time() >= bloque.hora_inicio
                and cita.hasta.time() <= bloque.hora_fin
            )
            # Si una cita empieza en los primeros 45 min del bloque, tapa su etiqueta: en Mi semana no se dibuja
            inicio_bloque = bloque.hora_inicio.hour * 60 + bloque.hora_inicio.minute
            bloque.etiqueta_tapada = any(
                cita.desde.date() == bloque.fecha
                and 0 <= cita.desde.hour * 60 + cita.desde.minute - inicio_bloque < 45
                for cita in citas
            )

        dias = []
        for fecha in (lunes + timedelta(days=i) for i in range(7)):
            del_dia = [bloque for bloque in bloques if bloque.fecha == fecha]
            dias.append({
                'fecha': fecha,
                'bloques': del_dia,
                'citas': [cita for cita in citas if cita.desde.date() == fecha],
                'es_hoy': fecha == hoy,
                'ya_paso': fecha < hoy,
                'total': texto_duracion(sum(bloque.minutos for bloque in del_dia)) if del_dia else '',
            })

        return {
            'dias': dias,
            'total_semana': texto_duracion(sum(bloque.minutos for bloque in bloques)),
            'dias_con_horario': sum(1 for dia in dias if dia['bloques']),
            'citas_semana': len(citas),
            'horas_grilla': [f'{hora:02d}:00' for hora in range(hora_inicio, hora_fin)],
            'hora_inicio_grilla': hora_inicio,
            'hora_fin_grilla': hora_fin,
            'lunes': lunes,
            'domingo': domingo,
            'semana_anterior': lunes - timedelta(days=7),
            'semana_siguiente': lunes + timedelta(days=7),
            'es_semana_actual': lunes == lunes_de(hoy),
            'se_puede_copiar': domingo >= hoy,  # no tiene sentido copiar a una semana que ya pasó
        }

    @staticmethod
    def fecha_sugerida(lunes, pedida=None):
        """La fecha del formulario "Nuevo bloque": la que se pidió (si no pasó), hoy si se mira la semana
        actual o, si no, el lunes de la semana elegida."""
        hoy = timezone.localdate()
        if pedida and pedida >= hoy:
            return pedida
        return max(lunes, hoy) if lunes + timedelta(days=6) >= hoy else lunes

    @staticmethod
    def copiar_semana(veterinario, lunes):
        """
        Copia los bloques de la semana anterior en la semana del lunes dado y devuelve (copiados, omitidos).
        Se saltan los días que ya pasaron y los bloques que se cruzarían con otros ya cargados.
        """
        hoy = timezone.localdate()
        propios = HorarioService.del_veterinario(veterinario)
        anteriores = propios.filter(fecha__range=(lunes - timedelta(days=7), lunes - timedelta(days=1)))
        if not anteriores:
            raise ValidationError('La semana anterior no tiene bloques para copiar.')

        copiados = omitidos = 0
        for bloque in anteriores:
            nuevo = HorarioVeterinario(veterinario=veterinario, fecha=bloque.fecha + timedelta(days=7),
                                       hora_inicio=bloque.hora_inicio, hora_fin=bloque.hora_fin)
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
        """Los servicios que atiende el veterinario. Los desactivados no se muestran en las casillas,
        así que se conservan como estaban."""
        inactivos = list(veterinario.servicios.filter(activo=False))
        veterinario.servicios.set(list(servicios) + inactivos)
        return len(servicios)

    @staticmethod
    def semana_de_la_clinica(lunes):
        """
        Para el administrador: una fila por veterinario activo y una columna por día, con sus bloques,
        las horas publicadas, las citas de la semana y la ocupación (minutos con cita sobre minutos de horario).
        """
        hoy = timezone.localdate()
        domingo = lunes + timedelta(days=6)
        fechas = [lunes + timedelta(days=i) for i in range(7)]
        veterinarios = list(
            get_user_model().objects.filter(rol=Roles.VETERINARIO, is_active=True)
            .prefetch_related('servicios').order_by('first_name', 'last_name', 'username')
        )
        bloques = list(HorarioVeterinario.objects.filter(fecha__range=(lunes, domingo)).order_by('hora_inicio'))
        citas = list(
            Cita.objects.filter(inicio__date__range=(lunes, domingo))
            .exclude(estado=EstadoCita.CANCELADA)
            .values_list('veterinario_id', 'inicio', 'fin')
        )

        filas = []
        for veterinario in veterinarios:
            suyos = [bloque for bloque in bloques if bloque.veterinario_id == veterinario.pk]
            for bloque in suyos:
                bloque.duracion = texto_duracion(minutos(bloque))
            minutos_horario = sum(minutos(bloque) for bloque in suyos)
            sus_citas = [(inicio, fin) for vet, inicio, fin in citas if vet == veterinario.pk]
            minutos_citas = sum((fin - inicio).total_seconds() // 60 for inicio, fin in sus_citas)
            filas.append({
                'veterinario': veterinario,
                'servicios': [servicio for servicio in veterinario.servicios.all() if servicio.activo],
                'dias': [
                    {'fecha': fecha, 'bloques': [b for b in suyos if b.fecha == fecha],
                     'es_hoy': fecha == hoy, 'ya_paso': fecha < hoy}
                    for fecha in fechas
                ],
                'total': texto_duracion(minutos_horario),
                'citas': len(sus_citas),
                'ocupacion': round(minutos_citas * 100 / minutos_horario) if minutos_horario else 0,
                'sin_horario': not suyos,
            })

        minutos_totales = sum(minutos(bloque) for bloque in bloques
                              if any(bloque.veterinario_id == fila['veterinario'].pk for fila in filas))
        minutos_ocupados = sum((fin - inicio).total_seconds() // 60 for _, inicio, fin in citas)
        return {
            'filas': filas,
            'fechas': [{'fecha': fecha, 'es_hoy': fecha == hoy, 'ya_paso': fecha < hoy} for fecha in fechas],
            'resumen': {
                'veterinarios': len(filas),
                'con_horario': sum(1 for fila in filas if not fila['sin_horario']),
                'horas': texto_duracion(minutos_totales),
                'citas': len(citas),
                'ocupacion': round(minutos_ocupados * 100 / minutos_totales) if minutos_totales else 0,
            },
            'lunes': lunes,
            'domingo': domingo,
            'semana_anterior': lunes - timedelta(days=7),
            'semana_siguiente': lunes + timedelta(days=7),
            'es_semana_actual': lunes == lunes_de(hoy),
        }
