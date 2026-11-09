"""Los usuarios de la clínica para el administrador: lista, reporte en CSV y cambio de rol."""
import csv

from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, UpdateView

from ..forms import UsuarioRolForm
from ..mixins import AdministradorRequeridoMixin, BusquedaMixin, CuentaGestionableMixin
from ..models import Roles
from ..services import UsuarioService


class ReporteUsuariosView(AdministradorRequeridoMixin, View):
    """Descarga las cuentas en CSV (sin contraseñas): lo que hace el botón "Descargar reporte"."""

    def get(self, request):
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = f'attachment; filename="woof-cuentas-{timezone.localdate():%Y-%m-%d}.csv"'
        respuesta.write('﻿')   # para que Excel lea bien las tildes
        csv.writer(respuesta).writerows(UsuarioService.filas_del_reporte())
        return respuesta


class UsuarioListView(AdministradorRequeridoMixin, BusquedaMixin, ListView):
    """Usuarios de la clínica para el administrador: buscador y filtro por rol (reemplaza al admin de Django)."""
    template_name = 'cuentas/panel/usuarios.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        return UsuarioService.buscar(self.buscar(), self.request.GET.get('rol', ''))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # "Editar" solo en las cuentas que quien mira puede gestionar
        UsuarioService.marcar_gestionables(self.request.user, contexto['usuarios'])
        contexto['buscar'] = self.buscar()
        contexto['rol_elegido'] = self.request.GET.get('rol', '')
        contexto['roles'] = Roles.choices
        return contexto


class UsuarioEditarView(AdministradorRequeridoMixin, CuentaGestionableMixin, SuccessMessageMixin, UpdateView):
    """Cambiar el rol de una cuenta (por ejemplo, darle el rol de veterinario) o desactivarla."""
    form_class = UsuarioRolForm
    template_name = 'cuentas/panel/usuario_editar.html'
    success_url = reverse_lazy('cuentas:usuarios')
    success_message = 'Se guardaron los cambios de %(persona)s.'

    def get_success_message(self, cleaned_data):
        return self.success_message % {'persona': self.object}
