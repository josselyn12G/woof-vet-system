"""python manage.py cargar_demo: crea los datos de demostración del Documento de Análisis (ver panel/services/demo.py)."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils.formats import date_format

from panel.services.demo import CLAVE_DEMO, PERSONAS, DemoService


class Command(BaseCommand):
    help = 'Carga los datos de demostración (veterinarios, clientes, mascotas, horarios, citas e historia clínica).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Necesario si la base no es SQLite (por ejemplo Neon): los datos quedan en esa base.',
        )

    def handle(self, *args, **opciones):
        # En Neon los datos quedan para todos: se pide confirmarlo a propósito
        if connection.vendor != 'sqlite' and not opciones['confirmar']:
            raise CommandError(
                f'La base es {connection.vendor} ({connection.settings_dict.get("HOST") or "local"}). '
                'Si de verdad quieres cargar la demo ahí, agrega --confirmar.'
            )
        if DemoService.ya_cargada():
            self.stdout.write(self.style.WARNING('La demo ya estaba cargada (existe el usuario paredes). No se cambió nada.'))
            return

        resumen = DemoService.cargar()
        self.stdout.write(self.style.SUCCESS(
            f'Demo cargada: {resumen["usuarios"]} usuarios, {resumen["mascotas"]} mascotas y {resumen["citas"]} citas.'
        ))
        self.stdout.write(f'Agenda de la Figura 1 (Dra. Paredes): {date_format(resumen["dia_figura"], "l j/m/Y")}.')
        self.stdout.write(f'Usuarios: {", ".join(username for username, *_ in PERSONAS)} · clave: {CLAVE_DEMO}')
