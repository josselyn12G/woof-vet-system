"""
Los correos de Woof (el código del login, los enlaces de la cuenta y los avisos de las citas y vacunas).

crear_correo() es la fábrica (patrón Factory) de todos ellos: recibe a quién, el asunto, la plantilla y los
datos, y devuelve el correo armado en texto y en HTML con el logo adentro, listo para .send(). Así quien
manda un correo no repite cómo se arma, y si cambia el formato (otro logo, otro remitente) cambia aquí solo.
"""
import smtplib
from email.mime.image import MIMEImage
from functools import lru_cache

from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

RUTA_LOGO = 'cuentas/img/logo-correo.png'

# Las fallas propias del envío: el servidor SMTP rechaza o se cae (SMTPException) o la red no responde a tiempo
# (OSError, que incluye los tiempos agotados). Solo estas activan el plan B; un error de programación (una
# plantilla rota, por ejemplo) no se esconde: sale como error para que se corrija.
FALLAS_DEL_CORREO = (smtplib.SMTPException, OSError)


def saludo(usuario):
    """Cómo se saluda en los correos: "Hola, Ana" (el nombre de pila o, si no lo tiene, el usuario)."""
    return usuario.first_name or usuario.username


@lru_cache(maxsize=1)
def bytes_del_logo():
    """
    El logo se lee del disco una sola vez por proceso y después se reutiliza en cada correo (una única
    instancia compartida, la idea del patrón Singleton). None si el archivo no está.
    """
    ruta = finders.find(RUTA_LOGO)
    if not ruta:
        return None
    with open(ruta, 'rb') as archivo:
        return archivo.read()


def adjuntar_logo(correo):
    """Pone el logo dentro del correo (no como adjunto aparte); la plantilla lo muestra con src="cid:logo-woof"."""
    correo.mixed_subtype = 'related'
    datos = bytes_del_logo()
    if datos is None:
        return
    logo = MIMEImage(datos)
    logo.add_header('Content-ID', '<logo-woof>')
    logo.add_header('Content-Disposition', 'inline', filename='logo-woof.png')
    correo.attach(logo)


def crear_correo(usuario, asunto, plantilla, contexto=None):
    """
    Arma un correo para el usuario con <plantilla>.txt y <plantilla>.html (por ejemplo 'cuentas/correos/codigo').
    Las dos plantillas reciben el contexto más 'nombre' (el saludo). No lo envía: devuelve el correo.
    """
    contexto = {'nombre': saludo(usuario), **(contexto or {})}
    correo = EmailMultiAlternatives(asunto, render_to_string(f'{plantilla}.txt', contexto), None, [usuario.email])
    correo.attach_alternative(render_to_string(f'{plantilla}.html', contexto), 'text/html')
    adjuntar_logo(correo)
    return correo


def enviar_correo_con_enlace(usuario, asunto, titulo, texto, boton, enlace, aviso):
    """Un correo con un botón (verificar el correo, crear una contraseña nueva...) con las plantillas de enlace."""
    crear_correo(usuario, asunto, 'cuentas/correos/enlace', {
        'titulo': titulo, 'texto': texto, 'boton': boton, 'enlace': enlace, 'aviso': aviso,
    }).send()
