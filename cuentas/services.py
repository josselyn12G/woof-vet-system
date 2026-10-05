import secrets
import time
from email.mime.image import MIMEImage

from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

MINUTOS_VALIDEZ = 5


def generar_codigo():
    """Devuelve un código de 6 dígitos, generado de forma segura."""
    codigo = secrets.randbelow(1_000_000)
    return f'{codigo:06d}'


def enviar_codigo(request, usuario):
    """Genera un código, lo guarda en la sesión con su vencimiento y lo envía al correo del usuario."""
    codigo = generar_codigo()
    vence = time.time() + MINUTOS_VALIDEZ * 60
    request.session['codigo_2fa'] = codigo
    request.session['codigo_2fa_vence'] = vence

    # Los datos que usan las dos plantillas del correo
    contexto = {
        'nombre': usuario.first_name or usuario.username,
        'codigo': codigo,
        'minutos': MINUTOS_VALIDEZ,
    }
    texto = render_to_string('cuentas/correos/codigo.txt', contexto)
    html = render_to_string('cuentas/correos/codigo.html', contexto)

    # Un correo con dos versiones: texto plano (por si el programa no muestra HTML) y HTML
    correo = EmailMultiAlternatives('Tu código de acceso a Woof', texto, None, [usuario.email])
    correo.attach_alternative(html, 'text/html')
    correo.mixed_subtype = 'related'           # el logo viaja dentro del correo, no como adjunto aparte

    # El logo va incrustado: el HTML lo muestra con src="cid:logo-woof"
    ruta_logo = finders.find('cuentas/img/logo-correo.png')
    if ruta_logo:
        with open(ruta_logo, 'rb') as archivo:
            logo = MIMEImage(archivo.read())
        logo.add_header('Content-ID', '<logo-woof>')
        logo.add_header('Content-Disposition', 'inline', filename='logo-woof.png')
        correo.attach(logo)

    correo.send()
