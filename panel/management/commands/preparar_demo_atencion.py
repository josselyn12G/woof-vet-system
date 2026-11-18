"""
Prepara la demo del flujo de atención del veterinario, justo antes de presentarla:

    python manage.py preparar_demo_atencion --confirmar

Llena el horario del veterinario esta semana y la siguiente con citas de las mascotas de los clientes (las de
días pasados, atendidas; las que vienen, confirmadas) y crea, con la hora actual, una cita que ya empezó (para
marcarla como atendida) y dos más tarde, de las mascotas del cliente elegido. Se puede correr las veces que haga
falta: borra la demo anterior que siga abierta. Al terminar imprime el recorrido paso a paso.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from cuentas.models import Roles
from mascotas.models import Mascota
from panel.services.demo import DemoAtencionService


class Command(BaseCommand):
    help = 'Crea una cita que ya empezó (y dos más) para mostrar el flujo de atención del veterinario.'

    def add_arguments(self, parser):
        parser.add_argument('--veterinario', default='dra.paredes', help='Usuario del veterinario (dra.paredes).')
        parser.add_argument('--cliente', default='ana.perez', help='Usuario del cliente dueño de las mascotas (ana.perez).')
        parser.add_argument('--confirmar', action='store_true',
                            help='Necesario fuera de SQLite: los datos quedan en la base compartida (Neon).')

    def handle(self, *args, **opciones):
        if connection.vendor != 'sqlite' and not opciones['confirmar']:
            raise CommandError('Esto escribe en la base compartida (Neon). Si de verdad quieres, agrega --confirmar.')
        Usuario = get_user_model()
        try:
            veterinario = Usuario.objects.get(username=opciones['veterinario'], rol=Roles.VETERINARIO)
            cliente = Usuario.objects.get(username=opciones['cliente'], rol=Roles.CLIENTE)
        except Usuario.DoesNotExist as error:
            raise CommandError(f'No encontré a ese veterinario o cliente: {error}') from error
        mascotas = list(Mascota.objects.filter(dueno=cliente).order_by('nombre'))
        if not mascotas:
            raise CommandError(f'{cliente.username} no tiene mascotas.')

        todas = list(Mascota.objects.filter(dueno__rol=Roles.CLIENTE).order_by('nombre'))
        semana = DemoAtencionService.llenar_semana(veterinario, todas)
        citas = DemoAtencionService.preparar(veterinario, mascotas)
        primera = citas[0]
        self.stdout.write(self.style.SUCCESS(f'Demo lista: horario lleno de esta semana y la siguiente con {semana} citas, y hoy:'))
        for cita in citas:
            self.stdout.write(f'  · {timezone.localtime(cita.inicio):%H:%M}  {cita.mascota} · {cita.servicio} · «{cita.motivo}»')
        self.stdout.write(f'''
Recorrido (entra como {veterinario.username}):
  1. Panel principal: "Citas hoy" y "Hoy" muestran la cita de {primera.mascota} a las {timezone.localtime(primera.inicio):%H:%M}.
  2. Agenda y citas → la cita de {primera.mascota} → botón «Atendida» (POST: queda como atendida).
  3. En la misma cita aparece «Registrar consulta» → diagnóstico, peso, receta (medicamento, dosis, cada cuántas
     horas y días) y vacunas con su próxima dosis → Guardar.
  4. Consultas médicas: la cita ya no está "Por registrar"; la consulta sale en "Consultas registradas".
  5. Entra como {cliente.username}: Historia clínica (la consulta en el Historial), Mis recetas (el tratamiento,
     sus días para tachar en el pop-up) y la campana con el aviso.
''')
