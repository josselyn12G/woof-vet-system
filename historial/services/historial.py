"""
La historia clínica de cada mascota: sus consultas (con receta), el tablero y registrar una consulta.

El carnet de vacunas vive en carnet.py (CarnetService) y el tratamiento en tratamiento.py (TratamientoService):
cada servicio tiene una sola razón para cambiar.
"""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from citas.models import EstadoCita
from compartido.graficos import grafico_de_peso
from historial.models import Consulta, VacunaAplicada
from mascotas.models import Mascota

from .carnet import AL_DIA, PROXIMA, REFORZADA, VENCIDA, CarnetService


class HistorialService:
    """
    La historia clínica de cada mascota: sus consultas (con receta) y sus vacunas.

    Las vistas del veterinario (registrar consulta), del cliente y del administrador (ver la historia)
    leen de aquí, así la consulta a la base vive en un solo lugar.
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
            'vacunas': CarnetService.carnet(mascota),
            # Lo que el dueño tiene que darle hoy: va arriba de todo, bien a la vista
            'tratamientos': [
                receta for consulta in consultas for receta in consulta.prescripciones.all() if receta.en_curso
            ],
        }

    @staticmethod
    def tablero(mascota, consultas, hoy=None):
        """
        Lo que muestran las tarjetas de la historia (y el PDF): cifras, el estado del carnet, el peso en cada
        consulta (las últimas 6, para el gráfico de barras) y la próxima vacuna con cuánto falta.
        Recibe las consultas ya cargadas (de_la_mascota) para no volver a pedirlas.
        """
        hoy = hoy or timezone.localdate()
        carnet = CarnetService.carnet(mascota, hoy)
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
            'grafico_peso': grafico_de_peso(barras),
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
    def mascota_elegida(mascotas, pedida):
        """
        La mascota de ?mascota=<id>, solo si está entre las del cliente; si no (vacío, inventado o ajeno), None.
        Así un id de otra persona nunca muestra nada suyo.
        """
        return mascotas.filter(pk=pedida).first() if str(pedida or '').isdigit() else None

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
