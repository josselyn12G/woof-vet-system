from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from cuentas.forms import RegistroForm
from cuentas.services import enviar_codigo


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = 'cuentas/registro.html'
    success_url = reverse_lazy('cuentas:login')


class LoginDosPasosView(LoginView):
    """Primer paso del login: valida usuario y contraseña, pero en vez de iniciar sesión envía un código al correo."""
    template_name = 'cuentas/login.html'

    def form_valid(self, form):
        usuario = form.get_user()
        self.request.session['pre_2fa_user'] = usuario.pk           # la sesión es JSON: se guarda el pk, no el objeto
        self.request.session['pre_2fa_next'] = self.get_success_url()  # a dónde ir al terminar (respeta ?next=)
        enviar_codigo(self.request, usuario)
        return redirect('cuentas:verificar')

