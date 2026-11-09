from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from citas.services.horarios import semana_pedida
from cuentas.mixins import (
    AdministradorRequeridoMixin, ClienteRequeridoMixin, SuperadminRequeridoMixin, VeterinarioRequeridoMixin,
)

from .mixins import PeriodoMixin
from .services import (
    PERIODOS_ADMINISTRADOR, PERIODOS_VETERINARIO, PanelAdministradorService, PanelClienteService,
    PanelSuperadminService, PanelVeterinarioService,
)


class PanelView(LoginRequiredMixin, View):
    """Después del login, manda a cada usuario a la portada de su rol. No dibuja nada: solo redirige."""

    def get(self, request):
        if request.user.es_veterinario:
            return redirect('panel:inicio_veterinario')
        if request.user.es_superadmin:
            return redirect('panel:inicio_superadmin')
        if request.user.es_administrador:
            return redirect('panel:inicio_administrador')
        return redirect('panel:inicio_cliente')  # el cliente es el rol por defecto


class InicioClienteView(ClienteRequeridoMixin, TemplateView):
    template_name = 'panel/inicio_cliente.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelClienteService.resumen(self.request.user))
        return contexto


class InicioVeterinarioView(VeterinarioRequeridoMixin, PeriodoMixin, TemplateView):
    template_name = 'panel/inicio_veterinario.html'
    periodos = PERIODOS_VETERINARIO
    periodo_por_defecto = '7d'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # ?semana= mueve "Mi semana" a otra semana (cualquier día sirve; una fecha inventada vuelve a la actual)
        lunes = semana_pedida(self.request.GET.get('semana'))
        contexto.update(PanelVeterinarioService.resumen(self.request.user, self.periodo()[1], lunes))
        return contexto


class InicioAdministradorView(AdministradorRequeridoMixin, PeriodoMixin, TemplateView):
    template_name = 'panel/inicio_administrador.html'
    periodos = PERIODOS_ADMINISTRADOR
    periodo_por_defecto = 'mes'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelAdministradorService.resumen(self.periodo()[1]))
        return contexto


class InicioSuperadminView(SuperadminRequeridoMixin, TemplateView):
    template_name = 'panel/inicio_superadmin.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelSuperadminService.resumen())
        return contexto
