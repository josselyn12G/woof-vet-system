from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from citas.models import EstadoCita
from historial.models import Consulta, Prescripcion, Vacuna, VacunaAplicada
from mascotas.models import Mascota

# Una vacuna cuya próxima dosis cae dentro de estos días aparece como «próxima» en el carnet
DIAS_PARA_PROXIMA = 30

# Estado de cada línea del carnet: (clave para el CSS, texto que se muestra)
AL_DIA = ('al_dia', 'Al día')
PROXIMA = ('proxima', 'Próxima')
VENCIDA = ('vencida', 'Vencida')
REFORZADA = ('reforzada', 'Reforzada')


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
        return {
            'consultas': list(consultas),
            'vacunas': list(vacunas.filter(mascota=mascota)),
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
            'proxima_vacuna': proxima,
            'total_recetas': len(recetas),
            'recetas_en_curso': sum(
                1 for r in recetas if r.fecha_inicio <= ahora < r.fecha_inicio + timedelta(days=r.duracion_dias)
            ),
        }

    @staticmethod
    def carnet_en_datos(lineas):
        """Las líneas del carnet como datos simples, para que el librito 3D (carnet-3d.js) las dibuje."""
        return [
            {
                'vacuna': aplicada.vacuna.nombre,
                'fecha': aplicada.fecha_aplicacion.strftime('%d/%m/%Y'),
                'lote': aplicada.lote or '—',
                'proxima': aplicada.proxima_dosis.strftime('%d/%m/%Y') if aplicada.proxima_dosis else '—',
                'veterinario': aplicada.veterinario.get_full_name() or aplicada.veterinario.username,
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
    def recetas_del_cliente(cliente, mascota=None, ahora=None):
        """
        Mis recetas: las líneas de receta de las mascotas del cliente, agrupadas por mascota
        [(mascota, [receta, ...]), ...], de la más nueva a la más vieja. Cada receta trae cuándo termina
        (inicio + días) y si sigue en curso. Con mascota, solo las de esa mascota.
        """
        ahora = ahora or timezone.now()
        recetas = (
            Prescripcion.objects.filter(consulta__mascota__dueno=cliente)
            .select_related('consulta__mascota__especie', 'consulta__veterinario')
            .order_by('consulta__mascota__nombre', '-fecha_inicio', 'pk')
        )
        if mascota is not None:
            recetas = recetas.filter(consulta__mascota=mascota)

        por_mascota = {}
        for receta in recetas:
            receta.termina = receta.fecha_inicio + timedelta(days=receta.duracion_dias)
            receta.en_curso = receta.fecha_inicio <= ahora < receta.termina
            por_mascota.setdefault(receta.consulta.mascota, []).append(receta)
        return list(por_mascota.items())

    @staticmethod
    def vacunas_para(mascota):
        """Las vacunas activas que se le pueden aplicar: las de su especie y las que sirven para todas."""
        return Vacuna.objects.filter(Q(especie__isnull=True) | Q(especie=mascota.especie_id), activa=True)

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
