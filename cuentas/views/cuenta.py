"""La cuenta de cada usuario: Mi cuenta (HU-22), cambiar la contraseña (HU-21), verificar el correo (HU-13)
y los términos (HU-23). Recuperar la contraseña (HU-14) usa las vistas de Django (ver urls.py)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, UpdateView

from ..forms import CambiarContrasenaForm, MiCuentaForm
from ..services import enviar_verificacion, verificar_correo


class MiCuentaView(LoginRequiredMixin, UpdateView):
    """Sus propios datos (cualquier rol). Si cambia el correo, queda sin verificar y se le envía el enlace."""
    form_class = MiCuentaForm
    template_name = 'cuentas/mi_cuenta.html'
    success_url = reverse_lazy('cuentas:mi_cuenta')

    def get_object(self, queryset=None):
        return self.request.user   # siempre la cuenta de quien inició sesión: no hay id en la URL

    def form_valid(self, form):
        cambio_el_correo = form.cambio_el_correo()
        if cambio_el_correo:
            form.instance.correo_verificado = False
        respuesta = super().form_valid(form)
        if cambio_el_correo and enviar_verificacion(self.request, self.object):
            messages.success(self.request, f'Guardamos tus datos. Te enviamos un enlace a {self.object.email} '
                                           'para verificar el correo nuevo.')
        else:
            messages.success(self.request, 'Guardamos tus datos.')
        return respuesta


class CambiarContrasenaView(LoginRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    """Pide la actual y la nueva dos veces. Django mantiene la sesión iniciada después del cambio."""
    form_class = CambiarContrasenaForm
    template_name = 'cuentas/cambiar_contrasena.html'
    success_url = reverse_lazy('cuentas:mi_cuenta')
    success_message = 'Cambiaste tu contraseña.'


class ReenviarVerificacionView(LoginRequiredMixin, View):
    """POST desde Mi cuenta: vuelve a enviar el enlace para verificar el correo."""
    http_method_names = ['post']

    def post(self, request):
        if request.user.correo_verificado:
            messages.info(request, 'Tu correo ya está verificado.')
        elif enviar_verificacion(request, request.user):
            messages.success(request, f'Te enviamos el enlace a {request.user.email}. Revisa también el spam.')
        else:
            messages.error(request, 'No pudimos enviar el correo. Inténtalo otra vez en unos minutos.')
        return redirect('cuentas:mi_cuenta')


class VerificarCorreoView(View):
    """El enlace del correo (público: puede abrirse sin sesión). Muestra si quedó verificado o si ya no sirve."""

    def get(self, request, uidb64, token):
        usuario = verificar_correo(uidb64, token)
        return render(request, 'cuentas/acceso/correo_verificado.html', {'usuario': usuario},
                      status=200 if usuario else 400)


class TerminosView(TemplateView):
    template_name = 'cuentas/acceso/terminos.html'
