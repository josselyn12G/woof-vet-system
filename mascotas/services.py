from io import BytesIO

from PIL import Image, ImageOps

# La foto se guarda reducida para que la base no crezca: ~50-100 KB en vez de varios MB
LADO_MAXIMO_FOTO = 800
CALIDAD_FOTO = 80


def preparar_foto(archivo):
    """Recibe la imagen subida (ya validada por el formulario) y devuelve los bytes en WEBP."""
    archivo.seek(0)
    imagen = Image.open(archivo)
    imagen = ImageOps.exif_transpose(imagen)  # gira las fotos de celular según su orientación real
    imagen.thumbnail((LADO_MAXIMO_FOTO, LADO_MAXIMO_FOTO))  # achica sin deformar; nunca agranda

    # WEBP solo acepta RGB o RGBA: se conserva la transparencia de los PNG
    if imagen.mode not in ('RGB', 'RGBA'):
        con_transparencia = 'A' in imagen.getbands() or 'transparency' in imagen.info
        imagen = imagen.convert('RGBA' if con_transparencia else 'RGB')

    salida = BytesIO()
    imagen.save(salida, 'WEBP', quality=CALIDAD_FOTO)
    return salida.getvalue()
