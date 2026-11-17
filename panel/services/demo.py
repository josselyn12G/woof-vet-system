"""
Datos de demostración para la defensa y para probar a mano: el ejemplo del Documento de Análisis.

Todo es relativo a hoy, así la demo funciona cualquier día: el próximo día hábil la Dra. Paredes tiene la
agenda de la Figura 1 (Luna, Kira, Simba y Toby cancelada), y las dos semanas anteriores tienen citas
cerradas con consultas, recetas, vacunas y calificaciones para los indicadores y la historia clínica.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario, Servicio
from citas.services import AgendaService
from cuentas.models import Ciudad, PerfilVeterinario, Roles
from historial.models import Consulta, Prescripcion, Vacuna, VacunaAplicada
from mascotas.models import Especie, Mascota, Raza

CLAVE_DEMO = 'Woof-Demo-2026'

# (usuario, nombre, apellido, rol)
PERSONAS = [
    ('laura', 'Laura', 'Gómez', Roles.ADMINISTRADOR),
    ('paredes', 'Sofía', 'Paredes', Roles.VETERINARIO),
    ('leon', 'Mateo', 'León', Roles.VETERINARIO),
    ('ruiz', 'Valeria', 'Ruiz', Roles.VETERINARIO),
    ('mora', 'Andrés', 'Mora', Roles.VETERINARIO),
    ('ana', 'Ana', 'Pérez', Roles.CLIENTE),
    ('carlos', 'Carlos', 'Mena', Roles.CLIENTE),
    ('maria', 'María', 'Torres', Roles.CLIENTE),
    ('luis', 'Luis', 'Andrade', Roles.CLIENTE),
]

# (usuario, especialidad, años de experiencia, verificado). Mora sigue sin verificar: no aparece al agendar
PERFILES = [
    ('paredes', 'Medicina general', 9, True),
    ('leon', 'Dermatología', 6, True),
    ('ruiz', 'Cirugía', 8, True),
    ('mora', 'Medicina general', 1, False),
]

# (nombre, duración, precio, activo, veterinarios), como el prototipo de la Figura 23
SERVICIOS = [
    ('Consulta general', 30, '25.00', True, ['paredes', 'leon', 'ruiz', 'mora']),
    ('Vacunación', 20, '18.00', True, ['paredes', 'leon']),
    ('Desparasitación', 20, '15.00', True, ['paredes', 'leon', 'ruiz']),
    ('Control post-operatorio', 30, '20.00', True, ['ruiz']),
    ('Peluquería', 60, '22.00', True, ['leon']),
    ('Limpieza dental', 45, '40.00', False, []),
    ('Nutrición', 40, '28.00', True, ['paredes']),
]

# (dueño, nombre, especie, raza, sexo, nacimiento, peso)
MASCOTAS = [
    ('ana', 'Milo', 'perro', 'Border Collie', 'M', date(2024, 3, 10), '12.80'),
    ('ana', 'Rocky', 'perro', 'Bóxer', 'M', date(2021, 7, 2), '28.40'),
    ('carlos', 'Kira', 'perro', 'Husky Siberiano', 'H', date(2022, 1, 15), '21.00'),
    ('maria', 'Simba', 'gato', 'Persa', 'M', date(2023, 9, 1), '4.20'),
    ('maria', 'Luna', 'perro', 'Golden Retriever', 'H', date(2020, 5, 20), '30.10'),
    ('luis', 'Toby', 'perro', 'Beagle', 'M', date(2019, 11, 8), '11.50'),
]

# Bloques de cada veterinario en los días hábiles: [(desde, hasta), ...]
HORARIOS = {
    'paredes': [(time(9, 0), time(13, 0)), (time(15, 0), time(18, 0))],
    'leon': [(time(9, 0), time(13, 0))],
    'ruiz': [(time(14, 0), time(18, 0))],
}


def cedula_valida(numero):
    """Una cédula ecuatoriana válida (provincia 17, módulo 10) armada con un número: siempre la misma."""
    base = f'170{numero:06d}'
    suma = 0
    for digito, coeficiente in zip(base, [2, 1, 2, 1, 2, 1, 2, 1, 2]):
        producto = int(digito) * coeficiente
        suma += producto - 9 if producto > 9 else producto
    return base + str((10 - suma % 10) % 10)


def dias_habiles(desde, hasta):
    dia = desde
    while dia <= hasta:
        if dia.weekday() < 5:
            yield dia
        dia += timedelta(days=1)


def proximo_dia_habil(fecha):
    fecha += timedelta(days=1)
    while fecha.weekday() >= 5:
        fecha += timedelta(days=1)
    return fecha


class DemoService:

    @staticmethod
    def ya_cargada():
        return get_user_model().objects.filter(username='paredes').exists()

    @staticmethod
    @transaction.atomic
    def cargar(hoy=None):
        """Crea todo en una transacción: si algo falla, la base queda como estaba. Devuelve un resumen."""
        hoy = hoy or timezone.localdate()
        usuarios = DemoService._personas()
        servicios = DemoService._servicios(usuarios)
        mascotas = DemoService._mascotas(usuarios)
        DemoService._horarios(usuarios, hoy - timedelta(days=14), hoy + timedelta(days=14))
        dia_figura = proximo_dia_habil(hoy)
        DemoService._agenda_de_la_figura_1(usuarios, servicios, mascotas, dia_figura)
        DemoService._historial(usuarios, servicios, mascotas, hoy)
        return {
            'usuarios': len(usuarios),
            'mascotas': len(mascotas),
            'citas': Cita.objects.filter(veterinario__username__in=HORARIOS).count(),
            'dia_figura': dia_figura,
        }

    # ---------- Partes ----------
    @staticmethod
    def _personas():
        modelo = get_user_model()
        quito = Ciudad.objects.filter(nombre='Quito').first()   # la carga la migración de Ecuador
        usuarios = {}
        for numero, (username, nombre, apellido, rol) in enumerate(PERSONAS, start=1):
            usuarios[username] = modelo.objects.create_user(
                username=username, email=f'{username}@woof.ec', password=CLAVE_DEMO, first_name=nombre,
                last_name=apellido, rol=rol, telefono=f'+5939870000{numero:02d}', cedula=cedula_valida(numero),
                ciudad=quito, correo_verificado=True, terminos_aceptados_en=timezone.now(),
            )
        for username, especialidad, anios, verificado in PERFILES:
            PerfilVeterinario.objects.create(usuario=usuarios[username], especialidad=especialidad,
                                             anios_experiencia=anios, verificado=verificado)
        return usuarios

    @staticmethod
    def _servicios(usuarios):
        servicios = {}
        for nombre, duracion, precio, activo, veterinarios in SERVICIOS:
            # get_or_create: si la clínica ya tiene ese servicio, no se le cambia nada
            servicio, _ = Servicio.objects.get_or_create(
                nombre=nombre, defaults={'duracion_min': duracion, 'precio': Decimal(precio), 'activo': activo},
            )
            servicio.veterinarios.add(*(usuarios[username] for username in veterinarios))
            servicios[nombre] = servicio
        return servicios

    @staticmethod
    def _mascotas(usuarios):
        mascotas = {}
        for dueno, nombre, codigo, raza, sexo, nacimiento, peso in MASCOTAS:
            especie = Especie.objects.get(codigo=codigo)
            mascotas[nombre] = Mascota.objects.create(
                dueno=usuarios[dueno], nombre=nombre, especie=especie,
                raza=Raza.objects.filter(especie=especie, nombre=raza).first(), sexo=sexo,
                fecha_nacimiento=nacimiento, peso_kg=Decimal(peso),
            )
        return mascotas

    @staticmethod
    def _horarios(usuarios, desde, hasta):
        HorarioVeterinario.objects.bulk_create([
            HorarioVeterinario(veterinario=usuarios[username], fecha=dia, hora_inicio=inicio, hora_fin=fin)
            for dia in dias_habiles(desde, hasta)
            for username, bloques in HORARIOS.items()
            for inicio, fin in bloques
        ])

    @staticmethod
    def _agenda_de_la_figura_1(usuarios, servicios, mascotas, dia):
        """§2.1: ese día la Dra. Paredes tiene a Luna, Kira y Simba, y a Toby cancelado. Se agendan con
        AgendaService, como lo haría el cliente, así pasan por las mismas reglas del Core."""
        paredes = usuarios['paredes']
        consulta, desparasitacion = servicios['Consulta general'], servicios['Desparasitación']
        for nombre, hora, servicio in (('Luna', time(9, 30), consulta), ('Kira', time(10, 0), consulta),
                                       ('Simba', time(12, 0), desparasitacion), ('Toby', time(11, 0), consulta)):
            cita = AgendaService.agendar(mascota=mascotas[nombre], veterinario=paredes, servicio=servicio,
                                         inicio=timezone.make_aware(datetime.combine(dia, hora)),
                                         motivo='Control anual' if nombre != 'Simba' else 'Desparasitación trimestral')
            if nombre == 'Toby':
                AgendaService.cancelar(cita)

    @staticmethod
    def _historial(usuarios, servicios, mascotas, hoy):
        """
        Las dos semanas anteriores: citas atendidas (con consulta, receta, vacuna y calificación),
        una inasistencia y una cancelada, para la historia clínica, el carnet y los indicadores.
        """
        paredes, leon = usuarios['paredes'], usuarios['leon']
        consulta, vacunacion = servicios['Consulta general'], servicios['Vacunación']
        rabia = Vacuna.objects.filter(nombre='Rabia', especie__codigo='perro').first()
        triple = Vacuna.objects.filter(nombre='Triple felina').first()
        pasados = list(dias_habiles(hoy - timedelta(days=14), hoy - timedelta(days=1)))

        # (días hábiles atrás, mascota, veterinario, servicio, hora, estado, diagnóstico, receta, vacuna, estrellas)
        visitas = [
            (8, 'Milo', paredes, consulta, time(9, 0), EstadoCita.ATENDIDA, 'Traqueobronquitis leve. Sin fiebre.',
             [('Amoxicilina 250 mg', '1 tableta', 12, 7), ('Jarabe antitusivo', '5 ml', 8, 5)], None, 5),
            (7, 'Rocky', leon, vacunacion, time(10, 0), EstadoCita.ATENDIDA, 'Sano. Se aplica el refuerzo anual.',
             [], rabia, 4),
            (6, 'Simba', paredes, vacunacion, time(10, 0), EstadoCita.ATENDIDA, 'Sano. Vacuna anual al día.',
             [], triple, 5),
            (5, 'Kira', paredes, consulta, time(11, 0), EstadoCita.NO_ASISTIO, '', [], None, None),
            (4, 'Luna', leon, consulta, time(9, 30), EstadoCita.ATENDIDA, 'Dermatitis alérgica leve en el lomo.',
             [('Prednisolona 5 mg', '1 tableta', 24, 5)], None, None),
            (3, 'Toby', paredes, consulta, time(15, 0), EstadoCita.CANCELADA, '', [], None, None),
            (2, 'Milo', paredes, consulta, time(9, 30), EstadoCita.ATENDIDA, 'Control: la tos mejoró.', [], rabia, 4),
        ]
        for atras, nombre, veterinario, servicio, hora, estado, diagnostico, receta, vacuna, estrellas in visitas:
            dia = pasados[-atras] if len(pasados) >= atras else hoy - timedelta(days=atras)
            inicio = timezone.make_aware(datetime.combine(dia, hora))
            # En el pasado no se puede agendar: se crea directo, ya cerrada (como si se hubiera atendido)
            cita = Cita.objects.create(
                mascota=mascotas[nombre], veterinario=veterinario, servicio=servicio, inicio=inicio,
                fin=inicio + timedelta(minutes=servicio.duracion_min), precio=servicio.precio, estado=estado,
                motivo='Control' if servicio == consulta else 'Vacuna anual',
            )
            if estado != EstadoCita.ATENDIDA:
                continue
            visita = Consulta.objects.create(
                cita=cita, mascota=cita.mascota, veterinario=veterinario, fecha=inicio, motivo=cita.motivo,
                peso_kg=cita.mascota.peso_kg, diagnostico=diagnostico,
                indicaciones='Agua fresca siempre disponible. Volver a control si empeora.',
            )
            for medicamento, dosis, cada, dias in receta:
                Prescripcion.objects.create(consulta=visita, medicamento=medicamento, dosis=dosis,
                                            frecuencia_horas=cada, duracion_dias=dias, fecha_inicio=inicio)
            if vacuna is not None:
                VacunaAplicada.objects.create(mascota=cita.mascota, vacuna=vacuna, consulta=visita,
                                              veterinario=veterinario, fecha_aplicacion=dia, lote='L-2026-11')
            if estrellas:
                AgendaService.calificar(cita, cita.mascota.dueno, estrellas,
                                        'Muy amable y explicó cada paso del tratamiento.')
