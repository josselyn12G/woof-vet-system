"""Las cifras de la portada de cada rol. Las vistas solo eligen el período y pasan el resultado a la plantilla."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from citas.models import Cita, EstadoCita, HorarioVeterinario, Servicio
from citas.services import CitaService, EstadisticasService, HorarioService, ServicioService
from cuentas.models import ROLES_DEL_PERSONAL, Roles
from mascotas.models import Mascota

def variacion(actual, anterior):
    """Cambio frente al período anterior. Sin datos para comparar no se inventa un porcentaje."""
    if anterior == 0:
        return {'texto': f'+{actual} nuevas' if actual else '—', 'tipo': 'nuevo' if actual else 'neutro'}
    cambio = (actual - anterior) * 100 / anterior
    return {'texto': f'{abs(cambio):.1f}%'.replace('.', ','), 'tipo': 'sube' if cambio > 0 else 'baja' if cambio < 0 else 'neutro'}


def grafico_de_linea(fechas, valores, ancho=1000, alto=210):
    """Arma en el servidor el SVG del gráfico de citas por día: la línea, el área, las guías y las etiquetas."""
    izquierda, derecha, arriba, abajo = 44, 16, 16, 34
    maximo = max(4, max(valores))                       # con 0 citas, el eje igual llega a 4 (se ve la línea en 0)
    paso_x = (ancho - izquierda - derecha) / max(len(valores) - 1, 1)
    alto_util = alto - arriba - abajo

    def punto(i, valor):
        return izquierda + i * paso_x, arriba + alto_util * (1 - valor / maximo)

    puntos = [punto(i, valor) for i, valor in enumerate(valores)]
    linea = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in puntos)
    area = f'{linea} L {puntos[-1][0]:.1f} {arriba + alto_util:.1f} L {puntos[0][0]:.1f} {arriba + alto_util:.1f} Z'
    guias = [{'y': round(arriba + alto_util * (1 - n / 4), 1), 'texto': round(maximo * n / 4)} for n in range(5)]
    cada = max(1, round(len(fechas) / 6))              # unas 6 o 7 fechas en el eje, sin amontonarlas
    etiquetas = [
        {'x': round(punto(i, 0)[0], 1), 'fecha': fecha}
        for i, fecha in enumerate(fechas) if i % cada == 0 or i == len(fechas) - 1
    ]
    return {'ancho': ancho, 'alto': alto, 'linea': linea, 'area': area, 'guias': guias, 'etiquetas': etiquetas,
            'base': arriba + alto_util, 'izquierda': izquierda, 'derecha': ancho - derecha}


def saludo(hora):
    if hora < 12:
        return 'Buenos días'
    if hora < 19:
        return 'Buenas tardes'
    return 'Buenas noches'


def por_rol():
    """Cuentas por rol con su porcentaje, para la barra de reparto."""
    cuentas = dict(get_user_model().objects.values_list('rol').annotate(total=Count('pk')))
    total = sum(cuentas.values())
    return total, [
        {'nombre': nombre, 'valor': cuentas.get(valor, 0), 'clase': valor,
         'porcentaje': round(cuentas.get(valor, 0) * 100 / total) if total else 0}
        for valor, nombre in Roles.choices
    ]


class PanelClienteService:
    @staticmethod
    def resumen(cliente):
        # Solo las mascotas de quien inició sesión; sin los bytes de la foto, pero sabiendo si tiene una
        mascotas = list(Mascota.objects.del_dueno(cliente).con_foto())
        # Qué tan completa está cada ficha: foto, raza, sexo, fecha de nacimiento y peso (datos reales)
        for mascota in mascotas:
            datos = [mascota.tiene_foto, mascota.raza, mascota.sexo, mascota.fecha_nacimiento, mascota.peso_kg]
            mascota.completa = round(sum(1 for dato in datos if dato) * 100 / len(datos))

        # La semana actual (lunes a domingo) con hoy marcado, y las próximas 4 citas para la línea de tiempo
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        proximas = CitaService.proximas_del_cliente(cliente)
        return {
            'mascotas': mascotas,
            # Las especies de sus mascotas, sin repetir y en el orden del catálogo (pestañas para filtrar)
            'especies': sorted({m.especie for m in mascotas}, key=lambda especie: (especie.orden, especie.nombre)),
            'hoy': hoy,
            'semana': [lunes + timedelta(days=i) for i in range(7)],
            'proximas_citas': proximas,
            # Para los accesos rápidos: la cita más cercana y cuántos servicios se pueden agendar
            'proxima_cita': proximas[0] if proximas else None,
            'servicios_disponibles': ServicioService.agendables().count(),
        }


class PanelVeterinarioService:
    @staticmethod
    def resumen(veterinario, dias, lunes):
        """Las cifras del período (los últimos N días) y la semana del lunes dado: horario y citas por día."""
        ahora = timezone.localtime()
        hoy = ahora.date()

        # Las cifras de los últimos N días (hasta hoy) y del período anterior las calcula el servicio de citas
        cifras = EstadisticasService.del_veterinario(veterinario, hoy - timedelta(days=dias - 1), hoy)

        return {
            'saludo': saludo(ahora.hour),
            'estadisticas': cifras['actual'],
            # Cambio frente al período anterior (sin datos anteriores no se inventa un porcentaje)
            'variaciones': {
                nombre: variacion(cifras['actual'][nombre], cifras['anterior'][nombre])
                for nombre in ('citas', 'atendidas', 'no_asistio')
            },
            'servicios_que_atiendo': veterinario.servicios.filter(activo=True).count(),
            'citas_hoy': Cita.objects.filter(veterinario=veterinario, inicio__date=hoy)
            .exclude(estado=EstadoCita.CANCELADA).count(),
            'grafico': grafico_de_linea(cifras['fechas'], cifras['citas_por_dia']),
            # Mi semana: los 7 días en columnas, con el horario de fondo y las citas reservadas encima
            'semana': HorarioService.semana_del_veterinario(veterinario, lunes),
        }


def pasos_para_abrir_la_agenda():
    """¿La clínica ya puede recibir citas? Veterinarios, servicios con quien los atienda y horarios publicados."""
    hay_veterinarios = get_user_model().objects.filter(rol=Roles.VETERINARIO, is_active=True).exists()
    pasos = [
        {'titulo': 'Registrar a los veterinarios', 'hecho': hay_veterinarios},
        {'titulo': 'Crear los servicios', 'hecho': ServicioService.agendables().exists()},
        {'titulo': 'Publicar los horarios', 'hecho': HorarioVeterinario.objects.filter(
            fecha__gte=timezone.localdate()).exists()},
    ]
    hechos = sum(paso['hecho'] for paso in pasos)
    return {'pasos': pasos, 'pasos_hechos': hechos, 'avance': round(hechos * 100 / len(pasos))}


class PanelAdministradorService:
    @staticmethod
    def resumen(dias):
        usuarios = get_user_model().objects
        hoy = timezone.localdate()

        # Período actual y el anterior, del mismo largo, para comparar
        desde = hoy - timedelta(days=dias - 1)
        desde_anterior = desde - timedelta(days=dias)

        def en_rango(consulta, campo, inicio, fin):
            return consulta.filter(**{f'{campo}__date__gte': inicio, f'{campo}__date__lte': fin}).count()

        nuevas = en_rango(usuarios.all(), 'date_joined', desde, hoy)
        nuevas_antes = en_rango(usuarios.all(), 'date_joined', desde_anterior, desde - timedelta(days=1))
        mascotas = en_rango(Mascota.objects.all(), 'creado', desde, hoy)
        mascotas_antes = en_rango(Mascota.objects.all(), 'creado', desde_anterior, desde - timedelta(days=1))
        veterinarios = usuarios.filter(rol=Roles.VETERINARIO).count()
        cifras = [
            {'etiqueta': 'Cuentas nuevas', 'icono': 'bi-person-plus', 'valor': nuevas,
             'variacion': variacion(nuevas, nuevas_antes)},
            {'etiqueta': 'Mascotas registradas', 'icono': 'bi-heart', 'valor': mascotas,
             'variacion': variacion(mascotas, mascotas_antes)},
            {'etiqueta': 'Clientes', 'icono': 'bi-people', 'valor': usuarios.filter(rol=Roles.CLIENTE).count(),
             'variacion': None},
            {'etiqueta': 'Veterinarios', 'icono': 'bi-heart-pulse', 'valor': veterinarios, 'variacion': None},
        ]

        # Gráfico: cuentas nuevas por día del período (datos reales)
        fechas = [desde + timedelta(days=i) for i in range(dias)]
        por_dia = {fecha: 0 for fecha in fechas}
        for unido in usuarios.filter(date_joined__date__gte=desde).values_list('date_joined', flat=True):
            fecha = timezone.localtime(unido).date()
            if fecha in por_dia:
                por_dia[fecha] += 1

        total, reparto = por_rol()
        return {
            'cifras': cifras,
            'grafico': grafico_de_linea(fechas, list(por_dia.values())),
            'nuevas_periodo': nuevas,
            'total_usuarios': total,
            'por_rol': reparto,
            'total_mascotas': Mascota.objects.count(),
            'total_veterinarios': veterinarios,
            'citas': CitaService.resumen_de_la_clinica(),
            'recientes': usuarios.order_by('-date_joined')[:8],
            **pasos_para_abrir_la_agenda(),
        }


class PanelSuperadminService:
    @staticmethod
    def resumen():
        """El personal de la clínica: cuántos hay de cada rol, a quién le falta algo y las cuentas recientes."""
        usuarios = get_user_model().objects
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        cuentas = usuarios.aggregate(
            administradores=Count('pk', filter=Q(rol=Roles.ADMINISTRADOR)),
            veterinarios=Count('pk', filter=Q(rol=Roles.VETERINARIO)),
            clientes=Count('pk', filter=Q(rol=Roles.CLIENTE)),
            desactivadas=Count('pk', filter=Q(is_active=False)),
        )
        cifras = [
            {'etiqueta': 'Administradores', 'icono': 'bi-shield-check', 'valor': cuentas['administradores']},
            {'etiqueta': 'Veterinarios', 'icono': 'bi-heart-pulse', 'valor': cuentas['veterinarios']},
            {'etiqueta': 'Clientes', 'icono': 'bi-people', 'valor': cuentas['clientes']},
            {'etiqueta': 'Cuentas desactivadas', 'icono': 'bi-person-dash', 'valor': cuentas['desactivadas']},
        ]

        # Veterinarios activos a los que les falta algo para recibir citas
        veterinarios = (
            usuarios.filter(rol=Roles.VETERINARIO, is_active=True)
            .annotate(
                servicios_activos=Count('servicios', filter=Q(servicios__activo=True), distinct=True),
                bloques_semana=Count('horarios', filter=Q(horarios__fecha__range=(lunes, lunes + timedelta(days=6))),
                                     distinct=True),
            )
            .order_by('first_name', 'last_name', 'username')
        )
        pendientes = [
            {'persona': vet, 'falta': ', '.join(falta)}
            for vet in veterinarios
            if (falta := [texto for texto, ok in (('sin servicios', vet.servicios_activos),
                                                   ('sin horario esta semana', vet.bloques_semana)) if not ok])
        ]

        total, reparto = por_rol()
        return {
            'cifras': cifras,
            'total_usuarios': total,
            'por_rol': reparto,
            'pendientes': pendientes,
            'veterinarios_listos': len(veterinarios) - len(pendientes),
            'total_veterinarios_activos': len(veterinarios),
            'servicios_activos': Servicio.objects.filter(activo=True).count(),
            'citas': CitaService.resumen_de_la_clinica(),
            'personal_reciente': usuarios.filter(rol__in=ROLES_DEL_PERSONAL).order_by('-date_joined')[:8],
            **pasos_para_abrir_la_agenda(),
        }
