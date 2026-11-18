from io import BytesIO

from PIL import Image, ImageOps

from mascotas.models import Mascota

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


def foto_visible(pk, usuario):
    """Los bytes de la foto de la mascota, o None si no tiene o el usuario no puede verla.

    La ve el dueño; también el personal: los veterinarios (Pacientes y agenda), el administrador
    y el superadministrador (gestión de mascotas) y quien entra a /admin/ (is_staff)."""
    mascotas = Mascota.objects.filter(pk=pk, foto__isnull=False)
    if not (usuario.is_staff or usuario.es_veterinario or usuario.gestiona_clinica):
        mascotas = mascotas.filter(dueno=usuario)
    foto = mascotas.values_list('foto', flat=True).first()
    return bytes(foto) if foto is not None else None
