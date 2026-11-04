"""Textos cortos que comparten las pantallas de citas (horario, agenda y Mi semana)."""
from datetime import datetime


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
