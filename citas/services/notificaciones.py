"""
Los avisos de las citas (F8): cada uno se guarda como Notificacion (la campana del panel) y sale por correo.

RF-23: al agendar, reprogramar o cancelar avisa al cliente y al veterinario.
RF-24: el recordatorio de 24 horas lo manda el comando enviar_recordatorios.
"""
import threading
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.formats import date_format

from citas.models import Cita, EstadoCita, Notificacion, TipoNotificacion

# El recordatorio sale para las citas que empiezan entre 23 y 25 horas desde ahora: si el comando corre
# cada hora, cada cita cae en la ventana al menos una vez (y la regla de la base evita repetirlo)
VENTANA_RECORDATORIO = (timedelta(hours=23), timedelta(hours=25))


def cuando(momento):
    """"martes 13 de octubre a las 10:30", en la hora de Ecuador."""
    return date_format(timezone.localtime(momento), r'l j \d\e F \a \l\a\s H:i')


def nombre(persona):
    return persona.get_full_name() or persona.username


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
    def enviar_sin_esperar(notificacion):
        """
        El correo sale en un hilo aparte: el SMTP puede tardar varios segundos por correo (EMAIL_TIMEOUT),
        y con dos avisos por cita la respuesta al agendar se quedaba esperando y parecía que no funcionaba.
        En las pruebas (AVISOS_EN_SEGUNDO_PLANO=False) se envía en el momento para poder revisar mail.outbox.
        """
        if not getattr(settings, 'AVISOS_EN_SEGUNDO_PLANO', True):
            notificacion.enviar()
            return

        def tarea():
            try:
                notificacion.enviar()
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
            f'Tu cita de {de_la_cita(cita)} con {nombre(cita.veterinario)} quedó confirmada para el '
            f'{cuando(cita.inicio)}. Precio: ${cita.precio}.',
            f'Tienes una cita nueva: {de_la_cita(cita)} (de {nombre(cita.mascota.dueno)}) el {cuando(cita.inicio)}.'
            + (f' Motivo: {cita.motivo}.' if cita.motivo else ''),
        )

    @staticmethod
    def cita_reprogramada(cita, inicio_anterior):
        cambio = f'pasó del {cuando(inicio_anterior)} al {cuando(cita.inicio)}'
        return NotificacionService.avisar_a_los_dos(
            cita, TipoNotificacion.REPROGRAMADA,
            f'Tu cita de {de_la_cita(cita)} con {nombre(cita.veterinario)} {cambio}. '
            f'La hora anterior quedó libre.',
            f'{nombre(cita.mascota.dueno)} reprogramó la cita de {de_la_cita(cita)}: {cambio}.',
        )

    @staticmethod
    def cita_cancelada(cita, cancelada_por, motivo=''):
        """Avisa quién la canceló; si fue la clínica (administración), también el motivo."""
        cliente = cita.mascota.dueno
        detalle = f'{de_la_cita(cita)} del {cuando(cita.inicio)}'
        if cancelada_por.pk == cliente.pk:
            para_el_cliente = f'Cancelaste la cita de {detalle} con {nombre(cita.veterinario)}.'
            para_el_veterinario = f'{nombre(cliente)} canceló la cita de {detalle}. El horario quedó libre.'
        else:
            motivo = motivo.strip()
            con_motivo = f' Motivo: {motivo}.' if motivo else ''
            para_el_cliente = (f'La clínica canceló tu cita de {detalle} con {nombre(cita.veterinario)}.{con_motivo} '
                               f'Puedes agendar otra cuando quieras.')
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
                    mensaje=f'Te recordamos la cita de {de_la_cita(cita)} con {nombre(cita.veterinario)} '
                            f'mañana, {cuando(cita.inicio)}. Si no puedes ir, cancélala o reprográmala en Woof.',
                )
        except IntegrityError:
            return None   # otra ejecución del comando ya lo creó
        notificacion.enviar()
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

    # ---------- La campana del panel ----------
    @staticmethod
    def no_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).count()

    @staticmethod
    def de(usuario, cantidad=50):
        return list(Notificacion.objects.filter(usuario=usuario).select_related('cita')[:cantidad])

    @staticmethod
    def marcar_leidas(usuario):
        return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
