"""
Modelos de mascotas, separados por tema como las vistas, los formularios y los services.
Django los encuentra porque se importan aquí; el resto del código sigue usando mascotas.models.<Modelo>.

- catalogo: las especies y razas (en la base, las edita el superadministrador).
- mascota: la ficha de la mascota.

validar_fecha_no_futura se exporta también porque la migración 0001 la usa como mascotas.models.validar_fecha_no_futura.
"""
from .catalogo import ESTILOS_DE_ESPECIE, RAZA_MESTIZO, Especie, Raza, RazaQuerySet
from .mascota import Mascota, MascotaQuerySet, Sexos, validar_fecha_no_futura

__all__ = [
    'ESTILOS_DE_ESPECIE', 'RAZA_MESTIZO', 'Especie', 'Mascota', 'MascotaQuerySet', 'Raza', 'RazaQuerySet', 'Sexos',
    'validar_fecha_no_futura',
]
