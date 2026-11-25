"""
python manage.py enviar_recordatorios

Manda el recordatorio de 24 horas (RF-24) a los clientes con una cita confirmada que empieza en 23 a 25 horas.
Está pensado para correr cada hora (en Render, un Cron Job con "0 * * * *"). Se puede ejecutar varias veces
seguidas sin repetir avisos: una cita que ya tiene su recordatorio no vuelve a recibirlo, y una cancelada
nunca lo recibe.

También avisa a los dueños cuando faltan 7 días o menos para la próxima dosis de una vacuna (HU-37), una sola
vez por dosis, y no si la mascota ya recibió otra dosis de esa vacuna.
"""
from django.core.management.base import BaseCommand

from citas.services import NotificacionService


class Command(BaseCommand):
    help = ('Envía el recordatorio de 24 horas a las citas confirmadas que empiezan en 23 a 25 horas '
            'y el de las vacunas cuya próxima dosis es dentro de 7 días o menos.')

    def handle(self, *args, **options):
        enviados = 0
        for cita in NotificacionService.citas_para_recordar():
            if NotificacionService.recordatorio(cita) is not None:
                enviados += 1
        self.stdout.write(self.style.SUCCESS(
            f'Se enviaron {enviados} recordatorio{"s" if enviados != 1 else ""}.'
        ))

        vacunas = 0
        for aplicada in NotificacionService.vacunas_para_recordar():
            if NotificacionService.recordatorio_vacuna(aplicada) is not None:
                vacunas += 1
        self.stdout.write(self.style.SUCCESS(
            f'Se enviaron {vacunas} recordatorio{"s" if vacunas != 1 else ""} de vacuna{"s" if vacunas != 1 else ""}.'
        ))
