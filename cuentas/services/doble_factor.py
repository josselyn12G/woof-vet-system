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

    contexto = {
        'nombre': usuario.first_name or usuario.username,
        'codigo': codigo,
        'minutos': MINUTOS_VALIDEZ,
    }
    texto = render_to_string('cuentas/correos/codigo.txt', contexto)
    html = render_to_string('cuentas/correos/codigo.html', contexto)

    correo = EmailMultiAlternatives('Tu código de acceso a Woof', texto, None, [usuario.email])
    correo.attach_alternative(html, 'text/html')
    correo.mixed_subtype = 'related'           # el logo viaja dentro del correo, no como adjunto aparte

    ruta_logo = finders.find('cuentas/img/logo-correo.png')
    if ruta_logo:
        with open(ruta_logo, 'rb') as archivo:
            logo = MIMEImage(archivo.read())
        logo.add_header('Content-ID', '<logo-woof>')
        logo.add_header('Content-Disposition', 'inline', filename='logo-woof.png')
        correo.attach(logo)

    correo.send()


def verificar_codigo(request, codigo_escrito):
    """Devuelve True si el código es correcto y no venció. Si es correcto, lo borra de la sesión."""
    codigo_guardado = request.session.get('codigo_2fa')
    vence = request.session.get('codigo_2fa_vence', 0)
    if not codigo_guardado or time.time() > vence:
        return False

    if not secrets.compare_digest(codigo_escrito.strip(), codigo_guardado):
        return False

    # El código coincide: se borra para que no se pueda usar dos veces
    del request.session['codigo_2fa']
    del request.session['codigo_2fa_vence']
    return True


def hay_login_pendiente(request):
    """True si alguien pasó la contraseña y su código todavía no vence."""
    return bool(request.session.get('pre_2fa_user')) and time.time() <= request.session.get('codigo_2fa_vence', 0)


def cancelar_login_pendiente(request):
    """Borra el "login a medias": quién pasó la contraseña, a dónde iba y su código."""
    for clave in ('pre_2fa_user', 'pre_2fa_next', 'codigo_2fa', 'codigo_2fa_vence'):
        request.session.pop(clave, None)
