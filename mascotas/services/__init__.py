"""
Lógica de mascotas fuera de las vistas.

- fotos: reducir la foto subida a WEBP y entregar la guardada a quien puede verla.
- mascotas: las consultas a la base (las del dueño, la búsqueda de la clínica y su resumen).
- catalogo: las especies y razas que se ofrecen al registrar una mascota.
"""
from .catalogo import CatalogoService
from .fotos import foto_visible, preparar_foto
from .mascotas import MascotaService

__all__ = ['CatalogoService', 'MascotaService', 'foto_visible', 'preparar_foto']
