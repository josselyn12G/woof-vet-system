"""
Los avisos de las citas (F8): cada uno se guarda como Notificacion (la campana del panel) y sale por correo.

RF-23: al agendar, reprogramar o cancelar avisa al cliente y al veterinario.
RF-24: el recordatorio de 24 horas lo manda el comando enviar_recordatorios.
HU-37: el mismo comando avisa al dueño una semana antes de la próxima dosis de cada vacuna.

Patrón fallback (como en «Mining microservice design patterns», SoCC 2022): el correo (Gmail por SMTP) es un
servicio externo que puede fallar. El aviso se guarda primero en la base, así que si el correo no sale la persona
igual lo ve en la campana (el plan B). El comando enviar_recordatorios reintenta esos correos más tarde, como
máximo MAX_INTENTOS_CORREO veces y nunca al instante: el artículo advierte que reintentar enseguida contra el
mismo servicio que acaba de fallar es un antipatrón.
"""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone
from django.utils.formats import date_format

from citas.models import Cita, EstadoCita, Notificacion, TipoNotificacion
from cuentas.services.correo import crear_correo
from historial.models import VacunaAplicada

# El recordatorio sale para las citas que empiezan entre 23 y 25 horas desde ahora: si el comando corre
# cada hora, cada cita cae en la ventana al menos una vez (y la regla de la base evita repetirlo)
VENTANA_RECORDATORIO = (timedelta(hours=23), timedelta(hours=25))

# El recordatorio de vacuna sale cuando faltan 7 días o menos para la próxima dosis (y todavía no pasó):
# si una vacuna se registra con la próxima dosis a 3 días, o el comando no corrió un día, igual se avisa
ANTICIPACION_VACUNA = timedelta(days=7)

# Reintentos del correo de un aviso que no salió (el plan B, la campana, ya lo tiene la persona):
# como máximo 3 intentos en total, el primero en el momento y los demás cuando corre el comando (cada hora),
# solo si pasó media hora desde que se creó el aviso y hasta 2 días después (luego ya no tiene sentido)
MAX_INTENTOS_CORREO = 3
ESPERA_ANTES_DE_REINTENTAR = timedelta(minutes=30)
VIGENCIA_DEL_REINTENTO = timedelta(days=2)

registro = logging.getLogger(__name__)


def cuando(momento):
    """"martes 13 de octubre a las 10:30", en la hora de Ecuador."""
    return date_format(timezone.localtime(momento), r'l j \d\e F \a \l\a\s H:i')


def que_dia(fecha):
    """"martes 1 de diciembre" (solo el día, para la próxima dosis de una vacuna)."""
    return date_format(fecha, r'l j \d\e F')


def en_cuantos_dias(fecha, hoy):
    dias = (fecha - hoy).days
    if dias == 0:
        return 'hoy'
    if dias == 1:
        return 'mañana'
    return f'en {dias} días'


def de_la_cita(cita):
    """"Consulta general para Milo" (lo que dicen todos los avisos)."""
    return f'{cita.servicio} para {cita.mascota}'


class NotificacionService:

    # ---------- Crear y enviar ----------
    @staticmethod
    def avisar(usuario, cita, tipo, mensaje):
        """Guarda el aviso (la campana lo ve enseguida) y lo manda por correo sin hacer esperar a nadie."""
        notificacion = Notificacion.objects.create(usuario=usuario, cita=cita, tipo=tipo, mensaje=mensaje)
        NotificacionService.enviar_sin_esperar(notificacion)
        return notificacion

    @staticmethod
    def enviar(notificacion):
        """
        Manda el aviso al correo del usuario. Devuelve True si salió.

        Si el correo falla (SMTP caído, dirección mala) no se rompe la cita: el aviso sigue guardado
        en la campana y el error queda en el registro del servidor. Con CORREO_AVISOS=False (Render)
        no se intenta enviar.

        Antes de enviar, el intento se "reserva" con un UPDATE condicional (bloqueo optimista): solo pasa si
        nadie más lo contó desde que se leyó el aviso. Así, si el hilo del primer envío y el comando de
        reintentos llegan a la vez, solo uno manda el correo. Se usa update() y no save() para no pisar
        otros campos que pudieron cambiar mientras tanto (por ejemplo leida, si la persona abrió la campana).
        """
        if not getattr(settings, 'CORREO_AVISOS', True):
            return False
        reservado = Notificacion.objects.filter(
            pk=notificacion.pk, correo_enviado=False, intentos_correo=notificacion.intentos_correo,
        ).update(intentos_correo=F('intentos_correo') + 1)
        if not reservado:
            return False   # ya salió o lo está enviando otro proceso
        notificacion.intentos_correo += 1

        correo = crear_correo(notificacion.usuario, f'Woof · {notificacion.get_tipo_display()}',
                              'citas/correos/notificacion', {'notificacion': notificacion})
        try:
            correo.send()
        except Exception:   # cualquier fallo del envío: se registra y la reserva sigue su curso
            registro.exception('No se pudo enviar la notificación %s a %s (intento %s de %s)', notificacion.pk,
                               notificacion.usuario.email, notificacion.intentos_correo, MAX_INTENTOS_CORREO)
            return False
        Notificacion.objects.filter(pk=notificacion.pk).update(correo_enviado=True)
        notificacion.correo_enviado = True
        return True

    @staticmethod
    def correos_para_reintentar(ahora=None):
        """
        Avisos cuyo correo no salió y que todavía vale la pena reintentar: con menos de MAX_INTENTOS_CORREO
        intentos, creados hace más de media hora y hace menos de 2 días, y sin una cita que ya empezó.
        """
        ahora = ahora or timezone.now()
        return (
            Notificacion.objects
            .filter(correo_enviado=False, intentos_correo__lt=MAX_INTENTOS_CORREO,
                    creado__lte=ahora - ESPERA_ANTES_DE_REINTENTAR, creado__gte=ahora - VIGENCIA_DEL_REINTENTO)
            .exclude(cita__inicio__lt=ahora)
            .select_related('usuario')
            .order_by('creado')
        )

    @staticmethod
    def reintentar_correos(ahora=None):
        """Vuelve a intentar los correos que no salieron (lo llama enviar_recordatorios). Devuelve cuántos salieron."""
        if not getattr(settings, 'CORREO_AVISOS', True):
            return 0   # con el correo apagado no hay nada que reintentar: los avisos ya están en la campana
        return sum(NotificacionService.enviar(aviso) for aviso in NotificacionService.correos_para_reintentar(ahora))

    @staticmethod
    def enviar_sin_esperar(notificacion):
        """
        El correo sale en un hilo aparte: el SMTP puede tardar varios segundos por correo (EMAIL_TIMEOUT),
        y con dos avisos por cita la respuesta al agendar se quedaba esperando y parecía que no funcionaba.
        En las pruebas (AVISOS_EN_SEGUNDO_PLANO=False) se envía en el momento para poder revisar mail.outbox.
        """
        if not getattr(settings, 'AVISOS_EN_SEGUNDO_PLANO', True):
            NotificacionService.enviar(notificacion)
            return

        def tarea():
            try:
                NotificacionService.enviar(notificacion)
            finally:
                connection.close()   # el hilo no deja conexiones abiertas a la base

        threading.Thread(target=tarea, name=f'aviso-{notificacion.pk}', daemon=True).start()

    @staticmethod
    def avisar_a_los_dos(cita, tipo, para_el_cliente, para_el_veterinario):
        cliente = cita.mascota.dueno
        return [
            NotificacionService.avisar(cliente, cita, tipo, para_el_cliente),
            NotificacionService.avisar(cita.veterinario, cita, tipo, para_el_veterinario),
        ]

    @staticmethod
    def al_confirmar(funcion, *args, **kwargs):
        """
        Avisa cuando la transacción termina bien (transaction.on_commit): si el cambio se deshace,
        nadie recibe un correo de una cita que no existe. Fuera de una transacción avisa enseguida.
        """
        transaction.on_commit(lambda: funcion(*args, **kwargs))

    # ---------- Cada aviso ----------
    @staticmethod
    def cita_agendada(cita):
        return NotificacionService.avisar_a_los_dos(
            cita, TipoNotificacion.AGENDADA,
            f'Tu cita de {de_la_cita(cita)} con {cita.veterinario.nombre_completo} quedó confirmada para el '
            f'{cuando(cita.inicio)}. Precio: ${cita.precio}.',
            f'Tienes una cita nueva: {de_la_cita(cita)} (de {cita.mascota.dueno.nombre_completo}) '
            f'el {cuando(cita.inicio)}.'
            + (f' Motivo: {cita.motivo}.' if cita.motivo else ''),
        )

    @staticmethod
    def cita_reprogramada(cita, inicio_anterior):
        cambio = f'pasó del {cuando(inicio_anterior)} al {cuando(cita.inicio)}'
        return NotificacionService.avisar_a_los_dos(
            cita, TipoNotificacion.REPROGRAMADA,
            f'Tu cita de {de_la_cita(cita)} con {cita.veterinario.nombre_completo} {cambio}. '
            f'La hora anterior quedó libre.',
            f'{cita.mascota.dueno.nombre_completo} reprogramó la cita de {de_la_cita(cita)}: {cambio}.',
        )

    @staticmethod
    def cita_cancelada(cita, cancelada_por, motivo=''):
        """Avisa quién la canceló; si fue la clínica (administración), también el motivo."""
        cliente = cita.mascota.dueno
        detalle = f'{de_la_cita(cita)} del {cuando(cita.inicio)}'
        if cancelada_por.pk == cliente.pk:
            para_el_cliente = f'Cancelaste la cita de {detalle} con {cita.veterinario.nombre_completo}.'
            para_el_veterinario = f'{cliente.nombre_completo} canceló la cita de {detalle}. El horario quedó libre.'
        else:
            motivo = motivo.strip()
            con_motivo = f' Motivo: {motivo}.' if motivo else ''
            para_el_cliente = (f'La clínica canceló tu cita de {detalle} con {cita.veterinario.nombre_completo}.'
                               f'{con_motivo} Puedes agendar otra cuando quieras.')
            para_el_veterinario = f'La clínica canceló la cita de {detalle}.{con_motivo} El horario quedó libre.'
        return NotificacionService.avisar_a_los_dos(cita, TipoNotificacion.CANCELADA, para_el_cliente,
                                                    para_el_veterinario)

    @staticmethod
    def recordatorio(cita):
        """El recordatorio de 24 horas, solo para el cliente (RF-24). None si ya se le había enviado."""
        try:
            with transaction.atomic():
                notificacion = Notificacion.objects.create(
                    usuario=cita.mascota.dueno, cita=cita, tipo=TipoNotificacion.RECORDATORIO,
                    mensaje=f'Te recordamos la cita de {de_la_cita(cita)} con {cita.veterinario.nombre_completo} '
                            f'mañana, {cuando(cita.inicio)}. Si no puedes ir, cancélala o reprográmala en Woof.',
                )
        except IntegrityError:
            return None   # otra ejecución del comando ya lo creó
        NotificacionService.enviar(notificacion)
        return notificacion

    @staticmethod
    def citas_para_recordar(ahora=None):
        """Confirmadas que empiezan en 23 a 25 horas y que todavía no tienen su recordatorio."""
        ahora = ahora or timezone.now()
        desde, hasta = (ahora + margen for margen in VENTANA_RECORDATORIO)
        return (
            Cita.objects.filter(estado=EstadoCita.CONFIRMADA, inicio__gte=desde, inicio__lte=hasta)
            .exclude(notificaciones__tipo=TipoNotificacion.RECORDATORIO)
            .select_related('mascota__dueno', 'veterinario', 'servicio')
        )

    @staticmethod
    def recordatorio_vacuna(aplicada, hoy=None):
        """El aviso de la próxima dosis, solo para el dueño (HU-37). None si ya se le había enviado."""
        hoy = hoy or timezone.localdate()
        mascota = aplicada.mascota
        try:
            with transaction.atomic():
                notificacion = Notificacion.objects.create(
                    usuario=mascota.dueno, vacuna_aplicada=aplicada, tipo=TipoNotificacion.VACUNA,
                    mensaje=f'A {mascota} le toca la próxima dosis de {aplicada.vacuna.nombre} '
                            f'{en_cuantos_dias(aplicada.proxima_dosis, hoy)}, el {que_dia(aplicada.proxima_dosis)}. '
                            f'Agenda su cita de vacunación en Woof para mantener su carnet al día.',
                )
        except IntegrityError:
            return None   # otra ejecución del comando ya lo creó
        NotificacionService.enviar(notificacion)
        return notificacion

    @staticmethod
    def vacunas_para_recordar(hoy=None):
        """
        Las dosis cuya próxima dosis cae entre hoy y dentro de 7 días, que todavía no tienen su recordatorio.
        Si la mascota ya recibió otra dosis de esa misma vacuna después, ya está al día y no se avisa.
        """
        hoy = hoy or timezone.localdate()
        dosis_posterior = VacunaAplicada.objects.filter(
            mascota=OuterRef('mascota'), vacuna=OuterRef('vacuna'), fecha_aplicacion__gt=OuterRef('fecha_aplicacion'),
        )
        return (
            VacunaAplicada.objects
            .filter(proxima_dosis__gte=hoy, proxima_dosis__lte=hoy + ANTICIPACION_VACUNA)
            .exclude(Exists(dosis_posterior))
            .exclude(notificaciones__tipo=TipoNotificacion.VACUNA)
            .select_related('mascota__dueno', 'vacuna')
            .order_by('proxima_dosis', 'pk')
        )

    # ---------- La campana del panel ----------
    @staticmethod
    def no_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).count()

    @staticmethod
    def de(usuario, cantidad=50):
        return list(Notificacion.objects.filter(usuario=usuario).select_related('cita')[:cantidad])

    @staticmethod
    def hace(momento, ahora=None):
        """'Ahora', 'Hace 5 min', 'Hace 2 h', 'Ayer' o la fecha ('12 nov'): lo que muestra el panel de la campana."""
        ahora = ahora or timezone.now()
        segundos = (ahora - momento).total_seconds()
        if segundos < 60:
            return 'Ahora'
        if segundos < 3600:
            return f'Hace {int(segundos // 60)} min'
        dias = (timezone.localtime(ahora).date() - timezone.localtime(momento).date()).days
        if dias == 0:
            return f'Hace {int(segundos // 3600)} h'
        if dias == 1:
            return 'Ayer'
        return date_format(timezone.localtime(momento), 'j M')

    @staticmethod
    def agrupadas(usuario, cantidad=30, ahora=None):
        """
        El panel de la campana: los últimos avisos en tres grupos [(clave, título, [aviso, ...]), ...]:
        hoy, esta semana (los 6 días anteriores) y antes. Cada aviso trae su 'hace' corto.
        """
        ahora = ahora or timezone.now()
        hoy = timezone.localtime(ahora).date()
        grupos = {'hoy': [], 'semana': [], 'antes': []}
        for aviso in NotificacionService.de(usuario, cantidad):
            aviso.hace = NotificacionService.hace(aviso.creado, ahora)
            dias = (hoy - timezone.localtime(aviso.creado).date()).days
            grupos['hoy' if dias == 0 else 'semana' if dias < 7 else 'antes'].append(aviso)
        return [('hoy', 'Hoy', grupos['hoy']), ('semana', 'Esta semana', grupos['semana']),
                ('antes', 'Antes', grupos['antes'])]

    @staticmethod
    def marcar_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
