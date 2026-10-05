from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from cuentas.forms import RegistroForm


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = 'cuentas/registro.html'
    success_url = reverse_lazy('cuentas:login')
