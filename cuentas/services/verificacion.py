"""HU-13: verificar el correo con un enlace firmado que llega al registrarse (o al cambiar el correo)."""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .correo import FALLAS_DEL_CORREO, enviar_correo_con_enlace

registro = logging.getLogger(__name__)


class TokenDeVerificacion(PasswordResetTokenGenerator):
    """
    Como el token de "recuperar contraseña", pero firmado con el correo y si ya está verificado:
    deja de servir en cuanto se usa o si el correo cambia. Vence a los 3 días (PASSWORD_RESET_TIMEOUT).
    """
    key_salt = 'cuentas.verificar-correo'

    def _make_hash_value(self, usuario, momento):
        return f'{usuario.pk}{usuario.email}{usuario.correo_verificado}{momento}'


token_de_verificacion = TokenDeVerificacion()


def enlace_de_verificacion(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    ruta = reverse('cuentas:verificar_correo', args=[uid, token_de_verificacion.make_token(usuario)])
    return request.build_absolute_uri(ruta)


def enviar_verificacion(request, usuario):
    """
    Envía el enlace para verificar el correo. Si el correo no sale (SMTP caído), no rompe el registro ni el cambio
    de datos: queda en el registro de errores y la persona puede pedirlo otra vez desde Mi cuenta.
    Devuelve True si se envió.
    """
    try:
        enviar_correo_con_enlace(
            usuario,
            asunto='Verifica tu correo en Woof',
            titulo='Verifica tu correo',
            texto='Confirma que este correo es tuyo para recibir los avisos de tus citas y poder recuperar tu contraseña.',
            boton='Verificar mi correo',
            enlace=enlace_de_verificacion(request, usuario),
            aviso='El enlace vence en 3 días. Si no creaste una cuenta en Woof, ignora este correo.',
        )
        return True
    except FALLAS_DEL_CORREO:   # SMTP caído, rechazo o tiempo agotado: se registra y se sigue
        registro.exception('No se pudo enviar la verificación del correo a %s', usuario.email)
        return False


def verificar_correo(uidb64, token):
    """El usuario del enlace con su correo ya verificado, o None si el enlace no es válido o venció."""
    try:
        usuario = get_user_model().objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        return None
    if usuario.correo_verificado:
        return usuario   # abrir el enlace dos veces no es un error
    if not token_de_verificacion.check_token(usuario, token):
        return None
    usuario.correo_verificado = True
    usuario.save(update_fields=['correo_verificado'])
    return usuario


def marcar_verificado(usuario):
    """El código del doble factor llega al correo: si alguien lo escribió bien, el correo es suyo."""
    if not usuario.correo_verificado:
        usuario.correo_verificado = True
        usuario.save(update_fields=['correo_verificado'])
