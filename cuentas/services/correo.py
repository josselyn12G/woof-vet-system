"""Lo que comparten los correos de Woof (el código del login y los avisos de las citas)."""
from email.mime.image import MIMEImage

from django.contrib.staticfiles import finders


def adjuntar_logo(correo):
    """Pone el logo dentro del correo (no como adjunto aparte); la plantilla lo muestra con src="cid:logo-woof"."""
    correo.mixed_subtype = 'related'
    ruta_logo = finders.find('cuentas/img/logo-correo.png')
    if not ruta_logo:
        return
    with open(ruta_logo, 'rb') as archivo:
        logo = MIMEImage(archivo.read())
    logo.add_header('Content-ID', '<logo-woof>')
    logo.add_header('Content-Disposition', 'inline', filename='logo-woof.png')
    correo.attach(logo)
