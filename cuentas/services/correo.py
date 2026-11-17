"""Lo que comparten los correos de Woof (el código del login, los enlaces de la cuenta y los avisos de las citas)."""
from email.mime.image import MIMEImage

from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


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


def enviar_correo_con_enlace(usuario, asunto, titulo, texto, boton, enlace, aviso):
    """
    Un correo con un botón (verificar el correo, crear una contraseña nueva...), en texto y en HTML con el logo.
    Usa las mismas plantillas para todos: cuentas/correos/enlace.txt y enlace.html.
    """
    contexto = {'nombre': usuario.first_name or usuario.username, 'titulo': titulo, 'texto': texto,
                'boton': boton, 'enlace': enlace, 'aviso': aviso}
    correo = EmailMultiAlternatives(asunto, render_to_string('cuentas/correos/enlace.txt', contexto), None,
                                    [usuario.email])
    correo.attach_alternative(render_to_string('cuentas/correos/enlace.html', contexto), 'text/html')
    adjuntar_logo(correo)
    correo.send()
