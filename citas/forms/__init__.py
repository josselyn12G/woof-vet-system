"""
Formularios de citas, separados por tema como las vistas. Solo validan la entrada; las consultas
con significado (¿lo atiende?, ¿se repite el nombre?) se las piden a los services.

- campos: campos que comparten varios formularios (veterinario en casillas o desplegable, selector de hora).
- catalogo: un servicio de la clínica.
- horarios: un bloque de Mi horario y los servicios que atiende el veterinario.
- agendar: la reserva del cliente.
- gestion: los filtros de la gestión de citas.
"""
from .agendar import AgendarCitaForm
from .campos import SelectorHora, VeterinarioCasillas, VeterinarioOpcion
from .catalogo import ServicioForm
from .gestion import FiltroCitasForm
from .horarios import HorarioForm, MisServiciosForm

__all__ = [
    'AgendarCitaForm', 'FiltroCitasForm', 'HorarioForm', 'MisServiciosForm', 'SelectorHora', 'ServicioForm',
    'VeterinarioCasillas', 'VeterinarioOpcion',
]
