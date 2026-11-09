"""
Modelos de citas, separados por tema como las vistas, los formularios y los services.
Django los encuentra porque se importan aquí; el resto del código sigue usando citas.models.<Modelo>.

- servicio: los servicios de la clínica y los veterinarios que los atienden.
- horario: los bloques de Mi horario del veterinario.
- cita: la reserva y sus estados (confirmada, atendida, no asistió, cancelada).
"""
from .cita import Cita, EstadoCita
from .horario import HorarioVeterinario
from .servicio import Servicio

__all__ = ['Cita', 'EstadoCita', 'HorarioVeterinario', 'Servicio']
