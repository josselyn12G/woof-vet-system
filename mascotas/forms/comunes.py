"""Límites y reglas de texto que comparten los formularios de mascotas."""
import re
from decimal import Decimal


TAMANO_MAXIMO_FOTO_MB = 5
FORMATOS_FOTO = ['jpg', 'jpeg', 'png', 'webp']  # los que muestran todos los navegadores
PESO_MAXIMO_KG = Decimal('150')
EDAD_MAXIMA_ANIOS = 35
# Letras (con tildes y ñ), espacios, guion, apóstrofo y punto: "Max", "Señor Bigotes", "Pastor Alemán"
SOLO_LETRAS = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ '.-]*$")

# Campos que el modelo deja en blanco (para el admin y los datos viejos) pero que el cliente debe llenar
CAMPOS_OBLIGATORIOS = ['nombre', 'especie', 'sexo', 'fecha_nacimiento', 'peso_kg']
MENSAJES_OBLIGATORIOS = {
    'nombre': 'Escribe el nombre de tu mascota.',
    'especie': 'Elige la especie.',
    'sexo': 'Elige si es macho o hembra.',
    'fecha_nacimiento': 'Indica la fecha de nacimiento (si no la sabes exacta, pon una aproximada).',
    'peso_kg': 'Indica el peso en kilogramos.',
}


def sin_espacios_de_mas(texto):
    return ' '.join(texto.split())
