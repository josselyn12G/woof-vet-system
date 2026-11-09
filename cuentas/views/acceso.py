"""La portada, el registro y el login en dos pasos (contraseña y luego el código)."""
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView

from ..forms import RegistroForm, VerificarCodigoForm
from ..services import (
    PoliticaDeCuentas, cancelar_login_pendiente, completar_login, hay_login_pendiente, iniciar_login_pendiente,
    verificar_codigo,
)


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = 'cuentas/registro.html'
    success_url = reverse_lazy('cuentas:login')


class LoginDosPasosView(LoginView):
    """Primer paso del login: valida usuario y contraseña, pero en vez de iniciar sesión envía un código al correo."""
    template_name = 'cuentas/login.html'

    def get(self, request, *args, **kwargs):
        # Volver al login (por ejemplo, con "Cancelar") empieza de cero: se descarta el login a medias
        cancelar_login_pendiente(request)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        # ?next= solo si esa página es del rol de quien entra; si no, a su panel
        usuario = getattr(self, 'usuario_que_entra', self.request.user)
        return PoliticaDeCuentas.destino_permitido(usuario, super().get_success_url())

    def form_valid(self, form):
        self.usuario_que_entra = form.get_user()
        # Con el doble factor apagado (Render), LoginView inicia sesión directo y va a ?next= o al panel
        if not settings.DOBLE_FACTOR:
            return super().form_valid(form)

        iniciar_login_pendiente(self.request, self.usuario_que_entra, self.get_success_url())
        return redirect('cuentas:verificar')


class VerificarView(FormView):
    template_name = 'cuentas/verificar.html'
    form_class = VerificarCodigoForm

    def dispatch(self, request, *args, **kwargs):
        # Solo se entra si se acaba de pasar la contraseña y el código sigue vigente (como LoginRequiredMixin en mascotas)
        if not hay_login_pendiente(request):
            cancelar_login_pendiente(request)
            return redirect('cuentas:login')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # El formulario ya validó el formato (6 dígitos); aquí se comprueba si el código es el correcto.
        if not verificar_codigo(self.request, form.cleaned_data['codigo']):
            form.add_error('codigo', 'El código es incorrecto o ya venció.')
            return self.form_invalid(form)

        return redirect(completar_login(self.request))
