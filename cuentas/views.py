from django.views.generic import TemplateView


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'
