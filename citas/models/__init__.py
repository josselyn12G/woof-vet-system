"""
Modelos de citas, separados por tema como las vistas, los formularios y los services.
Django los encuentra porque se importan aquí; el resto del código sigue usando citas.models.<Modelo>.

- servicio: los servicios de la clínica y los veterinarios que los atienden.
- horario: los bloques de Mi horario del veterinario.
- cita: la reserva y sus estados (confirmada, atendida, no asistió, cancelada).
- calificacion: las estrellas y el comentario del cliente sobre una cita atendida.
- notificacion: los avisos de las citas (campana del panel y correo).
"""
from .calificacion import ESTRELLAS_MAX, ESTRELLAS_MIN, Calificacion
from .cita import Cita, EstadoCita
from .horario import HorarioVeterinario
from .notificacion import Notificacion, TipoNotificacion
from .servicio import Servicio

__all__ = [
    'Calificacion', 'Cita', 'ESTRELLAS_MAX', 'ESTRELLAS_MIN', 'EstadoCita', 'HorarioVeterinario', 'Notificacion',
    'Servicio', 'TipoNotificacion',
]
