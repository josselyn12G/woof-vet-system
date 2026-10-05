from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView

from cuentas.forms import RegistroForm, VerificarCodigoForm
from cuentas.services import enviar_codigo, verificar_codigo


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


class VerificarView(FormView):
    template_name = 'cuentas/verificar.html'
    form_class = VerificarCodigoForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('pre_2fa_user'):
            return redirect('cuentas:login')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # El formulario ya validó el formato (6 dígitos); aquí se comprueba si el código es el correcto.
        if not verificar_codigo(self.request, form.cleaned_data['codigo']):
            form.add_error('codigo', 'El código es incorrecto o ya venció.')
            return self.form_invalid(form)

        # Se sacan de la sesión antes del login(), que cambia la llave de la sesión por seguridad
        pk = self.request.session.pop('pre_2fa_user')
        siguiente = self.request.session.pop('pre_2fa_next', '/')

        usuario = get_user_model().objects.get(pk=pk)
        login(self.request, usuario)
        return redirect(siguiente)
