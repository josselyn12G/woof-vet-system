"""
Lógica de las portadas fuera de las vistas.

- periodos: los períodos de las estadísticas (?periodo=).
- estadisticas: las cifras de la portada de cada rol (usa las apps de citas y mascotas).
"""
from .estadisticas import (
    PanelAdministradorService, PanelClienteService, PanelSuperadminService, PanelVeterinarioService, variacion,
)
from .periodos import PERIODOS_ADMINISTRADOR, PERIODOS_VETERINARIO, elegir_periodo, opciones_de_periodo

__all__ = [
    'PERIODOS_ADMINISTRADOR', 'PERIODOS_VETERINARIO', 'PanelAdministradorService', 'PanelClienteService',
    'PanelSuperadminService', 'PanelVeterinarioService', 'elegir_periodo', 'opciones_de_periodo', 'variacion',
]
