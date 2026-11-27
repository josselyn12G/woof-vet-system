import logging
import secrets
import time

from django.contrib.auth import get_user_model, login

from .correo import crear_correo
from .verificacion import marcar_verificado

MINUTOS_VALIDEZ = 5
# Quien ya tiene la contraseña no puede probar códigos sin fin: al sexto intento se cancela el login a medias
# y tiene que volver a poner la contraseña (que manda un código nuevo)
MAX_INTENTOS_CODIGO = 5
INTENTOS_AGOTADOS = 'Escribiste mal el código demasiadas veces. Ingresa tu contraseña otra vez para recibir uno nuevo.'
CODIGO_NO_ENVIADO = ('No pudimos enviarte el código a tu correo. Intenta de nuevo en unos minutos; '
                     'si sigue pasando, avisa a la clínica.')

registro = logging.getLogger(__name__)


def generar_codigo():
    """Devuelve un código de 6 dígitos, generado de forma segura."""
    codigo = secrets.randbelow(1_000_000)
    return f'{codigo:06d}'


def enviar_codigo(request, usuario):
    """
    Genera un código, lo guarda en la sesión con su vencimiento y lo envía al correo del usuario.
    Devuelve True si el correo salió.

    Si Gmail falla, no hay un plan B seguro (mostrar el código en pantalla anularía el doble factor):
    el error queda en el registro, el código se borra de la sesión y devuelve False para que el login
    avise a la persona en vez de caerse con un error 500.
    """
    codigo = generar_codigo()
    vence = time.time() + MINUTOS_VALIDEZ * 60
    request.session['codigo_2fa'] = codigo
    request.session['codigo_2fa_vence'] = vence
    request.session['codigo_2fa_intentos'] = 0   # cada código nuevo empieza con sus intentos

    try:
        crear_correo(usuario, 'Tu código de acceso a Woof', 'cuentas/correos/codigo',
                     {'codigo': codigo, 'minutos': MINUTOS_VALIDEZ}).send()
    except Exception:   # noqa: BLE001 (cualquier falla del SMTP)
        registro.exception('No se pudo enviar el código de acceso a %s', usuario.email)
        request.session.pop('codigo_2fa', None)
        request.session.pop('codigo_2fa_vence', None)
        return False
    return True


def verificar_codigo(request, codigo_escrito):
    """
    Devuelve True si el código es correcto y no venció. Si es correcto, lo borra de la sesión.

    Cada intento se cuenta. Pasados MAX_INTENTOS_CODIGO se cancela el login a medias (hay_login_pendiente()
    pasa a ser False) y la vista manda a la persona de vuelta al login.
    """
    intentos = request.session.get('codigo_2fa_intentos', 0) + 1
    request.session['codigo_2fa_intentos'] = intentos
    if intentos > MAX_INTENTOS_CODIGO:
        cancelar_login_pendiente(request)
        return False

    codigo_guardado = request.session.get('codigo_2fa')
    vence = request.session.get('codigo_2fa_vence', 0)
    if not codigo_guardado or time.time() > vence:
        return False

    if not secrets.compare_digest(codigo_escrito.strip(), codigo_guardado):
        return False

    # El código coincide: se borra para que no se pueda usar dos veces
    del request.session['codigo_2fa']
    del request.session['codigo_2fa_vence']
    del request.session['codigo_2fa_intentos']
    return True


def iniciar_login_pendiente(request, usuario, siguiente):
    """
    Primer paso: recuerda en la sesión quién pasó la contraseña y a dónde iba, y le envía el código.
    Devuelve False si el código no salió: entonces no queda ningún login a medias en la sesión.
    """
    request.session['pre_2fa_user'] = usuario.pk   # la sesión es JSON: se guarda el pk, no el objeto
    request.session['pre_2fa_next'] = siguiente    # a dónde ir al terminar (respeta ?next=)
    if enviar_codigo(request, usuario):
        return True
    cancelar_login_pendiente(request)
    return False


def completar_login(request):
    """Segundo paso, con el código ya verificado: inicia la sesión y devuelve a dónde ir.

    Los datos se sacan de la sesión antes del login(), que cambia la llave de la sesión por seguridad.
    """
    pk = request.session.pop('pre_2fa_user')
    siguiente = request.session.pop('pre_2fa_next', '/')
    usuario = get_user_model().objects.get(pk=pk)
    marcar_verificado(usuario)   # el código llegó a su correo: el correo es suyo (HU-13)
    login(request, usuario)
    return siguiente


def hay_login_pendiente(request):
    """True si alguien pasó la contraseña y su código todavía no vence."""
    return bool(request.session.get('pre_2fa_user')) and time.time() <= request.session.get('codigo_2fa_vence', 0)


def cancelar_login_pendiente(request):
    """Borra el "login a medias": quién pasó la contraseña, a dónde iba y su código."""
    for clave in ('pre_2fa_user', 'pre_2fa_next', 'codigo_2fa', 'codigo_2fa_vence', 'codigo_2fa_intentos'):
        request.session.pop(clave, None)
