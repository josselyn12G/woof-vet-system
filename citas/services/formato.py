"""Textos cortos que comparten las pantallas de citas (horario, agenda, Mi semana y la confirmación)."""
from datetime import datetime

from django.utils import timezone
from django.utils.formats import date_format


def minutos(bloque):
    """Minutos de un bloque del horario (hora de fin menos hora de inicio)."""
    inicio = datetime.combine(bloque.fecha, bloque.hora_inicio)
    return (datetime.combine(bloque.fecha, bloque.hora_fin) - inicio).seconds // 60


def texto_duracion(total):
    """180 -> "3 h", 90 -> "1 h 30 min", 45 -> "45 min"."""
    horas, resto = divmod(total, 60)
    if not horas and resto:
        return f'{resto} min'
    return f'{horas} h' + (f' {resto} min' if resto else '')


def plural(cantidad, palabra):
    """plural(1, "bloque") -> "1 bloque"; plural(3, "bloque") -> "3 bloques"."""
    return f'{cantidad} {palabra}{"s" if cantidad != 1 else ""}'


def datos_de_confirmacion(cita):
    """Lo que se ve en el pop-up de "cita agendada": mascota, servicio, día, hora y doctor."""
    inicio = timezone.localtime(cita.inicio)
    return {
        'titulo': f'{cita.mascota} tiene cita.',
        'detalle': f'{cita.servicio} con {cita.veterinario.get_full_name() or cita.veterinario.username}',
        'cuando': date_format(inicio, r'l j \d\e F, H:i'),
    }
