"""
Formularios de mascotas, separados por tema como las vistas. Solo validan la entrada; las consultas
con significado (¿se repite el nombre?, ¿qué especies se ofrecen?) se las piden a los services.

- comunes: límites (foto, peso, edad) y reglas de texto que comparten los formularios.
- mis_mascotas: la ficha que llena el cliente.
- gestion: la ficha de cualquier mascota, con su dueño (superadministrador).
- catalogo: las especies y razas.
"""
from .catalogo import EspecieForm, EspecieOpcion, RazaForm
from .gestion import DuenoOpcion, MascotaGestionForm
from .mis_mascotas import MascotaForm

__all__ = ['DuenoOpcion', 'EspecieForm', 'EspecieOpcion', 'MascotaForm', 'MascotaGestionForm', 'RazaForm']
