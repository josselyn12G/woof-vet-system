"""
Vistas de mascotas, separadas por tema como sus services. Solo reciben la petición, le piden los datos
a los services y responden; urls.py las sigue usando como views.<Vista>.

- mis_mascotas: «Mis mascotas» del cliente (CRUD, carnet y foto).
- gestion: todas las mascotas de la clínica (administrador) y su ficha completa (superadministrador).
- catalogo: las especies y razas (superadministrador).
"""
from .catalogo import (
    CatalogoEliminarView, EspecieCreateView, EspecieEliminarView, EspecieListView, EspecieUpdateView,
    RazaCreateView, RazaEliminarView, RazaUpdateView,
)
from .gestion import (
    MascotaGestionCreateView, MascotaGestionDeleteView, MascotaGestionDetailView, MascotaGestionListView,
    MascotaGestionUpdateView,
)
from .mis_mascotas import (
    FotoMascotaView, MascotaCarnetView, MascotaCreateView, MascotaDeleteView, MascotaDetailView, MascotaListView,
    MascotaUpdateView,
)

__all__ = [
    # mis_mascotas
    'MascotaListView', 'MascotaDetailView', 'MascotaCarnetView', 'MascotaCreateView', 'MascotaUpdateView',
    'MascotaDeleteView', 'FotoMascotaView',
    # gestion
    'MascotaGestionListView', 'MascotaGestionDetailView', 'MascotaGestionCreateView', 'MascotaGestionUpdateView',
    'MascotaGestionDeleteView',
    # catalogo
    'EspecieListView', 'EspecieCreateView', 'EspecieUpdateView', 'RazaCreateView', 'RazaUpdateView',
    'CatalogoEliminarView', 'EspecieEliminarView', 'RazaEliminarView',
]
