from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from citas.models import EstadoCita
from historial.models import Consulta, Prescripcion, TomaDia, Vacuna, VacunaAplicada
from mascotas.models import Mascota

# Una vacuna cuya próxima dosis cae dentro de estos días aparece como «próxima» en el carnet
DIAS_PARA_PROXIMA = 30

# Estado de cada línea del carnet: (clave para el CSS, texto que se muestra)
AL_DIA = ('al_dia', 'Al día')
PROXIMA = ('proxima', 'Próxima')
VENCIDA = ('vencida', 'Vencida')
REFORZADA = ('reforzada', 'Reforzada')

# Qué imagen lleva cada receta: se deduce de la dosis y del nombre (palabras clave → tipo, texto e ícono)
TIPOS_DE_MEDICAMENTO = [
    (('gota',), ('gotas', 'Gotas', 'bi-eyedropper')),
    (('jarabe', 'ml', 'suspensi'), ('jarabe', 'Jarabe', 'bi-cup-straw')),
    (('inyec', 'ampolla', 'jeringa'), ('inyeccion', 'Inyección', 'bi-prescription2')),
    (('crema', 'pomada', 'ungüento', 'gel'), ('crema', 'Crema', 'bi-bandaid')),
]
TABLETA = ('tableta', 'Tableta', 'bi-capsule-pill')

# Estado de cada día del tratamiento: (clave para el CSS, texto)
DIA_HECHO = ('hecho', 'Hecho')
DIA_HOY = ('hoy', 'Hoy')
DIA_SIN_MARCAR = ('sin_marcar', 'Sin marcar')
DIA_PROXIMO = ('proximo', 'Próximo')


class HistorialService:
    """
    La historia clínica de cada mascota: sus consultas (con receta) y sus vacunas.

    Las vistas del veterinario (registrar consulta), del cliente y del administrador (ver la historia)
    y el carnet de vacunación leen de aquí, así la consulta a la base vive en un solo lugar.
    """

    @staticmethod
    def de_la_mascota(mascota):
        """
        Las consultas de la mascota de la más nueva a la más vieja, cada una con su receta y sus vacunas,
        y todas sus vacunas aplicadas (también las cargadas sin consulta), para la línea de tiempo y el carnet.
        """
        vacunas = VacunaAplicada.objects.select_related('vacuna', 'veterinario')
        consultas = (
            Consulta.objects.filter(mascota=mascota)
            .select_related('veterinario', 'cita__servicio')
            .prefetch_related('prescripciones', Prefetch('vacunas_aplicadas', queryset=vacunas))
        )
        consultas = list(consultas)
        return {
            'consultas': consultas,
            # Con su estado (al día, próxima, vencida), como en el carnet
            'vacunas': HistorialService.carnet(mascota),
            # Lo que el dueño tiene que darle hoy: va arriba de todo, bien a la vista
            'tratamientos': [
                receta for consulta in consultas for receta in consulta.prescripciones.all() if receta.en_curso
            ],
        }

    @staticmethod
    def estado_de_la_vacuna(proxima_dosis, hoy=None):
        """
        «Vencida» si la próxima dosis ya pasó, «próxima» si falta menos de 30 días y «al día» en otro caso
        (también si la vacuna no lleva refuerzo).
        """
        hoy = hoy or timezone.localdate()
        if proxima_dosis is None:
            return AL_DIA
        if proxima_dosis < hoy:
            return VENCIDA
        if proxima_dosis - hoy < timedelta(days=DIAS_PARA_PROXIMA):
            return PROXIMA
        return AL_DIA

    @staticmethod
    def carnet(mascota, hoy=None):
        """
        Las líneas del carnet de vacunación (HU-36), de la más reciente a la más antigua: vacuna, fecha, lote,
        veterinario, próxima dosis y estado. También salen las vacunas que ya se desactivaron del catálogo.

        Solo la última dosis de cada vacuna lleva estado; las anteriores quedan como «reforzada»,
        así una dosis vieja ya renovada no aparece como vencida.
        """
        lineas = list(
            VacunaAplicada.objects.filter(mascota=mascota).select_related('vacuna', 'veterinario')
        )
        ya_vistas = set()
        for aplicada in lineas:   # vienen de la más nueva a la más vieja (ordering del modelo)
            if aplicada.vacuna_id in ya_vistas:
                aplicada.estado, aplicada.estado_texto = REFORZADA
            else:
                aplicada.estado, aplicada.estado_texto = HistorialService.estado_de_la_vacuna(
                    aplicada.proxima_dosis, hoy,
                )
                ya_vistas.add(aplicada.vacuna_id)
        return lineas

    @staticmethod
    def tablero(mascota, consultas, hoy=None):
        """
        Lo que muestran las tarjetas de la historia (y el PDF): cifras, el estado del carnet, el peso en cada
        consulta (las últimas 6, para el gráfico de barras) y la próxima vacuna con cuánto falta.
        Recibe las consultas ya cargadas (de_la_mascota) para no volver a pedirlas.
        """
        hoy = hoy or timezone.localdate()
        carnet = HistorialService.carnet(mascota, hoy)
        vigentes = [linea for linea in carnet if linea.estado != REFORZADA[0]]   # la última dosis de cada vacuna
        cuenta = {clave: sum(1 for linea in vigentes if linea.estado == clave) for clave, _ in (AL_DIA, PROXIMA, VENCIDA)}

        # Peso: de la consulta más vieja a la más nueva, con la altura de cada barra relativa a la más alta
        pesos = [(c.fecha, c.peso_kg) for c in reversed(consultas) if c.peso_kg][-6:]
        maximo = max((peso for _, peso in pesos), default=0)
        barras = [{'fecha': fecha, 'peso': peso, 'alto': round(float(peso) * 100 / float(maximo)) if maximo else 0}
                  for fecha, peso in pesos]

        # Próxima vacuna: la próxima dosis más cercana que todavía no pasó; el anillo marca cuánto del refuerzo ya corrió
        futuras = sorted((linea for linea in vigentes if linea.proxima_dosis and linea.proxima_dosis >= hoy),
                         key=lambda linea: linea.proxima_dosis)
        proxima = None
        if futuras:
            linea = futuras[0]
            total = (linea.proxima_dosis - linea.fecha_aplicacion).days or 1
            proxima = {'linea': linea, 'dias': (linea.proxima_dosis - hoy).days,
                       'avance': min(100, round((hoy - linea.fecha_aplicacion).days * 100 / total))}

        recetas = [receta for consulta in consultas for receta in consulta.prescripciones.all()]
        ahora = timezone.now()
        return {
            'carnet': carnet,
            'vigentes': vigentes,
            'estado_carnet': [
                {'clave': clave, 'texto': texto, 'cantidad': cuenta[clave],
                 'porcentaje': round(cuenta[clave] * 100 / len(vigentes)) if vigentes else 0}
                for clave, texto in (AL_DIA, PROXIMA, VENCIDA)
            ],
            'al_dia': cuenta[AL_DIA[0]],
            'barras_peso': barras,
            'grafico_peso': HistorialService.grafico_de_peso(barras),
            'vacunas_al_dia': round(cuenta[AL_DIA[0]] * 100 / len(vigentes)) if vigentes else 0,
            'cuenta_carnet': cuenta,
            'proxima_vacuna': proxima,
            'total_recetas': len(recetas),
            'recetas_en_curso': sum(
                1 for r in recetas if r.fecha_inicio <= ahora < r.fecha_inicio + timedelta(days=r.duracion_dias)
            ),
        }

    @staticmethod
    def historial_medico(consultas, carnet, hoy=None):
        """
        La línea de tiempo de la historia: cada consulta, cada vacuna aplicada y cada receta como un registro,
        de lo más nuevo a lo más viejo y agrupados por mes [(primer día del mes, [registro, ...]), ...].
        Cada registro sabe su tipo (para el filtro Todas / Consultas / Vacunas / Recetas) y su ícono.
        """
        hoy = hoy or timezone.localdate()
        ahora = timezone.now()
        registros = []
        for consulta in consultas:
            recetas = list(consulta.prescripciones.all())
            vacunas = list(consulta.vacunas_aplicadas.all())
            servicio = consulta.cita.servicio.nombre if consulta.cita_id else 'Consulta sin cita'
            registros.append({
                'tipo': 'consulta', 'icono': 'bi-clipboard2-pulse', 'cuando': consulta.fecha,
                'titulo': servicio, 'veterinario': consulta.veterinario, 'motivo': consulta.motivo,
                'insignia': f'{len(recetas)} receta{"s" if len(recetas) != 1 else ""}' if recetas else 'Atendida',
                'tono': 'acento' if recetas else 'neutro', 'consulta': consulta, 'recetas': recetas, 'vacunas': vacunas,
            })
            for receta in recetas:
                # en_curso es propiedad de Prescripcion; las que ya acabaron dicen «Terminado»
                insignia = 'En curso' if receta.en_curso else 'Por empezar' if ahora < receta.fecha_inicio else 'Terminado'
                registros.append({
                    'tipo': 'receta', 'icono': 'bi-capsule', 'cuando': receta.fecha_inicio,
                    'titulo': receta.medicamento, 'veterinario': consulta.veterinario,
                    'detalle': f'{receta.dosis} cada {receta.frecuencia_horas} h · {receta.duracion_dias} días',
                    'insignia': insignia, 'tono': 'ok' if receta.en_curso else 'acento' if insignia == 'Por empezar' else 'neutro',
                    'receta': receta, 'consulta': consulta,
                })
        for linea in carnet:
            cuando = timezone.make_aware(datetime.combine(linea.fecha_aplicacion, time(12, 0)))
            registros.append({
                'tipo': 'vacuna', 'icono': 'bi-shield-plus', 'cuando': cuando,
                'titulo': linea.vacuna.nombre, 'veterinario': linea.veterinario,
                'detalle': f'Vacuna · lote {linea.lote}' if linea.lote else 'Vacuna aplicada en la clínica',
                'insignia': 'Aplicada' if linea.estado != VENCIDA[0] else 'Refuerzo vencido',
                'tono': 'ok' if linea.estado != VENCIDA[0] else 'alerta', 'linea': linea,
            })
        registros.sort(key=lambda registro: registro['cuando'], reverse=True)
        por_mes = {}
        for registro in registros:
            mes = timezone.localtime(registro['cuando']).date().replace(day=1)
            por_mes.setdefault(mes, []).append(registro)
        return list(por_mes.items())

    @staticmethod
    def grafico_de_peso(barras, ancho=600, alto=180, margen=14):
        """
        Los puntos del gráfico de peso (SVG): x repartido a lo ancho y y entre el peso más bajo y el más alto.
        Con un solo registro, la línea queda plana de un borde al otro y el punto al final.
        Devuelve los puntos, la línea y el área de abajo (la plantilla los pinta con localize off: sin comas decimales).
        """
        if not barras:
            return None
        if len(barras) == 1:
            y = alto / 2
            punto = {'x': ancho - margen, 'y': y, 'peso': barras[0]['peso'], 'fecha': barras[0]['fecha']}
            return {
                'puntos': [punto], 'linea': f'{margen},{y} {ancho - margen},{y}',
                'area': f'M{margen},{alto} L{margen},{y} L{ancho - margen},{y} L{ancho - margen},{alto} Z',
                'ancho': ancho, 'alto': alto, 'ultimo': punto,
            }
        pesos = [float(barra['peso']) for barra in barras]
        minimo, maximo = min(pesos), max(pesos)
        rango = (maximo - minimo) or 1
        puntos = []
        for i, barra in enumerate(barras):
            x = ancho / 2 if len(barras) == 1 else margen + i * (ancho - 2 * margen) / (len(barras) - 1)
            y = alto / 2 if maximo == minimo else margen + (maximo - float(barra['peso'])) * (alto - 2 * margen) / rango
            puntos.append({'x': round(x, 1), 'y': round(y, 1), 'peso': barra['peso'], 'fecha': barra['fecha']})
        linea = ' '.join(f"{p['x']},{p['y']}" for p in puntos)
        area = f"M{puntos[0]['x']},{alto} L" + ' L'.join(f"{p['x']},{p['y']}" for p in puntos) + f" L{puntos[-1]['x']},{alto} Z"
        return {'puntos': puntos, 'linea': linea, 'area': area, 'ancho': ancho, 'alto': alto, 'ultimo': puntos[-1]}

    @staticmethod
    def carnet_en_datos(lineas):
        """Las líneas del carnet como datos simples, para que el librito 3D (carnet-3d.js) las dibuje."""
        return [
            {
                'vacuna': aplicada.vacuna.nombre,
                'fecha': aplicada.fecha_aplicacion.strftime('%d/%m/%Y'),
                'lote': aplicada.lote or '—',
                'proxima': aplicada.proxima_dosis.strftime('%d/%m/%Y') if aplicada.proxima_dosis else '—',
                'veterinario': aplicada.veterinario.nombre_completo,
                'estado': aplicada.estado,
                'estado_texto': aplicada.estado_texto,
            }
            for aplicada in lineas
        ]

    @staticmethod
    def mascota_elegida(mascotas, pedida):
        """
        La mascota de ?mascota=<id>, solo si está entre las del cliente; si no (vacío, inventado o ajeno), None.
        Así un id de otra persona nunca muestra nada suyo.
        """
        return mascotas.filter(pk=pedida).first() if str(pedida or '').isdigit() else None

    @staticmethod
    def tipo_de_medicamento(receta):
        """Tableta, jarabe, gotas, crema o inyección, según la dosis y el nombre (para su imagen)."""
        texto = f'{receta.medicamento} {receta.dosis}'.lower()
        for palabras, tipo in TIPOS_DE_MEDICAMENTO:
            if any(palabra in texto for palabra in palabras):
                return tipo
        return TABLETA

    @staticmethod
    def seguimiento(receta, hoy=None):
        """
        Los días del tratamiento con su estado (hecho, hoy, sin marcar o próximo), cuántas tomas tocan por día
        y el avance: días marcados sobre días del tratamiento. Usa receta.dias_marcados (mejor si ya vienen
        con prefetch_related).
        """
        hoy = hoy or timezone.localdate()
        inicio = timezone.localtime(receta.fecha_inicio).date()
        marcados = {toma.dia for toma in receta.dias_marcados.all()}
        dias = []
        for numero in range(receta.duracion_dias):
            dia = inicio + timedelta(days=numero)
            if dia in marcados:
                estado = DIA_HECHO
            elif dia == hoy:
                estado = DIA_HOY
            elif dia < hoy:
                estado = DIA_SIN_MARCAR
            else:
                estado = DIA_PROXIMO
            dias.append({'numero': numero + 1, 'fecha': dia, 'estado': estado[0], 'texto': estado[1],
                         'se_puede_marcar': dia <= hoy})
        hechos = sum(1 for dia in dias if dia['estado'] == DIA_HECHO[0])
        clave, texto, icono = HistorialService.tipo_de_medicamento(receta)
        return {
            'dias': dias,
            'hechos': hechos,
            'avance': round(hechos * 100 / receta.duracion_dias) if receta.duracion_dias else 0,
            'tomas_por_dia': max(1, 24 // receta.frecuencia_horas),
            'hoy_marcado': any(dia['estado'] == DIA_HECHO[0] and dia['fecha'] == hoy for dia in dias),
            'tipo': clave, 'tipo_texto': texto, 'icono': icono,
        }

    @staticmethod
    def marcar_dia(receta, dia, hoy=None):
        """
        Marca o desmarca un día del tratamiento (el check del dueño). Devuelve True si quedó marcado.
        Solo días del tratamiento y que ya llegaron: no se puede marcar por adelantado.
        """
        hoy = hoy or timezone.localdate()
        inicio = timezone.localtime(receta.fecha_inicio).date()
        if not inicio <= dia < inicio + timedelta(days=receta.duracion_dias):
            raise ValidationError('Ese día no es parte del tratamiento.')
        if dia > hoy:
            raise ValidationError('Todavía no llega ese día: márcalo cuando le des la dosis.')
        marcado = TomaDia.objects.filter(prescripcion=receta, dia=dia)
        if marcado.exists():
            marcado.delete()
            return False
        try:
            with transaction.atomic():
                TomaDia.objects.create(prescripcion=receta, dia=dia)
        except IntegrityError:
            pass   # dos clics a la vez: la base deja uno solo y el día queda marcado
        return True

    @staticmethod
    def guardar_dias(receta, dias, hoy=None):
        """
        Deja marcados exactamente esos días del tratamiento (lo que quedó en el pop-up al cerrarlo): un solo POST
        en lugar de uno por check. Los demás días se desmarcan. Solo días del tratamiento que ya llegaron.
        Devuelve cuántos quedaron marcados.
        """
        hoy = hoy or timezone.localdate()
        inicio = timezone.localtime(receta.fecha_inicio).date()
        fin = inicio + timedelta(days=receta.duracion_dias)
        dias = set(dias)
        for dia in dias:
            if not inicio <= dia < fin:
                raise ValidationError('Ese día no es parte del tratamiento.')
            if dia > hoy:
                raise ValidationError('Todavía no llega ese día: márcalo cuando le des la dosis.')
        with transaction.atomic():
            TomaDia.objects.filter(prescripcion=receta).exclude(dia__in=dias).delete()
            ya = set(TomaDia.objects.filter(prescripcion=receta).values_list('dia', flat=True))
            TomaDia.objects.bulk_create([TomaDia(prescripcion=receta, dia=dia) for dia in dias - ya],
                                        ignore_conflicts=True)
        return len(dias)

    @staticmethod
    def recetas_del_cliente(cliente, mascota=None, ahora=None, consulta=None):
        """
        Las líneas de receta de las mascotas del cliente, agrupadas por mascota
        [(mascota, [receta, ...]), ...], de la más nueva a la más vieja. Cada receta trae cuándo termina
        (inicio + días), si sigue en curso, su seguimiento y la siguiente toma.
        Con mascota, solo las de esa mascota; con consulta (id), solo las de esa consulta.
        """
        ahora = ahora or timezone.now()
        recetas = (
            Prescripcion.objects.filter(consulta__mascota__dueno=cliente)
            .select_related('consulta__mascota__especie', 'consulta__veterinario', 'consulta__cita__servicio')
            .prefetch_related('dias_marcados')
            .order_by('consulta__mascota__nombre', '-fecha_inicio', 'pk')
        )
        if mascota is not None:
            recetas = recetas.filter(consulta__mascota=mascota)
        if consulta is not None:
            recetas = recetas.filter(consulta_id=consulta)

        por_mascota = {}
        for receta in recetas:
            # termina y en_curso son propiedades de Prescripcion (cuándo acaba y si sigue)
            receta.por_empezar = ahora < receta.fecha_inicio
            receta.seguimiento = HistorialService.seguimiento(receta, timezone.localtime(ahora).date())
            receta.siguiente_toma = HistorialService.siguiente_toma(receta, ahora)
            receta.siguiente_dia = HistorialService.dia_relativo(receta.siguiente_toma, ahora)
            por_mascota.setdefault(receta.consulta.mascota, []).append(receta)
        return list(por_mascota.items())

    @staticmethod
    def dia_relativo(momento, ahora=None):
        """'Hoy', 'Mañana' o None (la plantilla pone la fecha): para leer de un vistazo la siguiente dosis."""
        if momento is None:
            return None
        hoy = timezone.localtime(ahora or timezone.now()).date()
        dias = (timezone.localtime(momento).date() - hoy).days
        return {0: 'Hoy', 1: 'Mañana'}.get(dias)

    @staticmethod
    def siguiente_toma(receta, ahora=None):
        """
        Cuándo toca la próxima dosis: el inicio más tantas veces la frecuencia como haga falta para pasar de ahora.
        None si el tratamiento ya terminó (o si la siguiente caería después del último día).
        """
        ahora = ahora or timezone.now()
        if ahora <= receta.fecha_inicio:
            return receta.fecha_inicio
        termina = receta.fecha_inicio + timedelta(days=receta.duracion_dias)
        paso = timedelta(hours=receta.frecuencia_horas)
        tomas_pasadas = -(-(ahora - receta.fecha_inicio) // paso)   # división hacia arriba
        toma = receta.fecha_inicio + tomas_pasadas * paso
        return toma if toma < termina else None

    @staticmethod
    def resumen_tratamiento(consulta, recetas):
        """
        Un tratamiento = las recetas de una consulta. Suma los días marcados de todas, dice su estado
        (en curso si alguna sigue, por empezar, o terminado) y la siguiente toma más cercana.
        """
        total = sum(receta.duracion_dias for receta in recetas)
        hechos = sum(receta.seguimiento['hechos'] for receta in recetas)
        if any(receta.en_curso for receta in recetas):
            estado = ('en_curso', 'En curso')
        elif all(receta.por_empezar for receta in recetas):
            estado = ('por_empezar', 'Por empezar')
        else:
            estado = ('terminado', 'Terminado')
        tomas = [receta.siguiente_toma for receta in recetas if receta.siguiente_toma]
        return {
            'consulta': consulta,
            'mascota': consulta.mascota,
            'titulo': consulta.cita.servicio.nombre if consulta.cita_id else 'Consulta',
            'recetas': recetas,
            'hechos': hechos,
            'total_dias': total,
            'avance': round(hechos * 100 / total) if total else 0,
            'estado': estado[0],
            'estado_texto': estado[1],
            'siguiente_toma': min(tomas) if tomas else None,
            'pendientes_hoy': [r for r in recetas if r.en_curso and not r.seguimiento['hoy_marcado']],
            'al_dia': estado[0] == 'en_curso' and all(r.seguimiento['hoy_marcado'] for r in recetas if r.en_curso),
        }

    @staticmethod
    def tratamientos_del_cliente(cliente, mascota=None, ahora=None, consulta=None):
        """
        Mis recetas: las recetas agrupadas por la consulta en que se recetaron (un tratamiento por consulta),
        de la consulta más nueva a la más vieja. Además, el resumen de hoy: los tratamientos en curso,
        el avance de todos ellos juntos y cada medicamento que toca hoy (dado o pendiente).
        """
        ahora = ahora or timezone.now()
        por_consulta = {}
        for _, recetas in HistorialService.recetas_del_cliente(cliente, mascota, ahora, consulta):
            for receta in recetas:
                por_consulta.setdefault(receta.consulta, []).append(receta)
        tratamientos = sorted(
            (HistorialService.resumen_tratamiento(c, rs) for c, rs in por_consulta.items()),
            key=lambda tratamiento: tratamiento['consulta'].fecha, reverse=True,
        )
        en_curso = [t for t in tratamientos if t['estado'] == 'en_curso']
        total = sum(t['total_dias'] for t in en_curso)
        hechos = sum(t['hechos'] for t in en_curso)
        # Cumplimiento de todos los tratamientos (también los terminados): días marcados sobre días recetados
        total_todos = sum(t['total_dias'] for t in tratamientos)
        hechos_todos = sum(t['hechos'] for t in tratamientos)
        return {
            'tratamientos': tratamientos,
            'en_curso': len(en_curso),
            'avance_en_curso': round(hechos * 100 / total) if total else 0,
            'cumplimiento': round(hechos_todos * 100 / total_todos) if total_todos else 0,
            'dias_marcados': hechos_todos,
            'dias_recetados': total_todos,
            'total_medicamentos': sum(len(t['recetas']) for t in tratamientos),
            'hoy': [(t, receta) for t in en_curso for receta in t['recetas'] if receta.en_curso],
            'pendientes_hoy': sum(len(t['pendientes_hoy']) for t in en_curso),
        }

    @staticmethod
    def vacunas_para(mascota):
        """Las vacunas activas que se le pueden aplicar: las de su especie y las que sirven para todas."""
        return Vacuna.objects.filter(Q(especie__isnull=True) | Q(especie=mascota.especie_id), activa=True)

    @staticmethod
    def vacunas_para_elegir(mascota, actual_pk=None):
        """Las del desplegable al registrar una vacuna: las que se le pueden aplicar y, al editar, la que ya tiene."""
        return Vacuna.objects.filter(
            Q(pk__in=HistorialService.vacunas_para(mascota)) | Q(pk=actual_pk)
        ).select_related('especie')

    @staticmethod
    def recetas_del_dueno(dueno):
        """Las recetas de las mascotas de esa persona: la de otro cliente no está en la consulta (404)."""
        return Prescripcion.objects.filter(consulta__mascota__dueno=dueno)

    @staticmethod
    def puede_registrar_consulta(cita):
        """Solo una cita atendida que todavía no tiene consulta (RF-20)."""
        return cita.estado == EstadoCita.ATENDIDA and not Consulta.objects.filter(cita=cita).exists()

    @staticmethod
    def consulta_de(cita):
        """
        La consulta de la cita para el formulario: la que ya tiene (para editarla) o una nueva sin guardar,
        con la cita, la mascota, el veterinario, la fecha y el motivo de la reserva ya puestos.
        """
        consulta = Consulta.objects.filter(cita=cita).first()
        if consulta is None:
            consulta = Consulta(cita=cita, mascota=cita.mascota, veterinario=cita.veterinario, fecha=cita.inicio,
                                motivo=cita.motivo)
        return consulta

    @staticmethod
    def fecha_de_la_cita(cita):
        """El día de la cita (en la hora de Ecuador): la fecha de aplicación de sus vacunas."""
        return timezone.localtime(cita.inicio).date()

    @staticmethod
    def guardar_consulta(consulta_form, recetas, vacunas):
        """
        Guarda la consulta, su receta y sus vacunas como una sola operación: si algo falla, no queda nada a medias.
        Los formularios ya vienen validados por la vista. Si se escribió el peso, pasa a ser el peso de la mascota.
        """
        with transaction.atomic():
            consulta = consulta_form.save()
            recetas.instance = consulta
            recetas.save()
            vacunas.instance = consulta
            vacunas.save()
            if consulta.peso_kg:
                # update(): solo cambia el peso, sin pasar por el formulario de la mascota
                Mascota.objects.filter(pk=consulta.mascota_id).update(peso_kg=consulta.peso_kg)
        return consulta
