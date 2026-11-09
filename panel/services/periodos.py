"""Los períodos de las estadísticas de las portadas (?periodo=)."""

PERIODOS_VETERINARIO = {'7d': ('7 días', 7), 'mes': ('1 mes', 30), '3m': ('3 meses', 90)}
PERIODOS_ADMINISTRADOR = {'7d': ('7 días', 7), 'mes': ('1 mes', 30), '3m': ('3 meses', 90), '6m': ('6 meses', 180)}


def elegir_periodo(clave, periodos, defecto):
    """La clave de ?periodo= si existe (un valor inventado vuelve al de siempre) y sus días."""
    if clave not in periodos:
        clave = defecto
    return clave, periodos[clave][1]


def opciones_de_periodo(periodos):
    return [(valor, nombre) for valor, (nombre, _) in periodos.items()]
