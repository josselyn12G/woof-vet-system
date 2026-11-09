"""El equipo de la clínica (administradores y veterinarios) que gestiona el superadministrador."""
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from ..forms import NuevaContrasenaForm, PersonalCreacionForm, PersonalForm
from ..mixins import BusquedaMixin, CuentaGestionableMixin, SuperadminRequeridoMixin
from ..models import ROLES_DEL_PERSONAL, Roles
from ..services import PoliticaDeCuentas, UsuarioService
from ..services.usuarios import ESTADOS_CUENTA


class EquipoListView(SuperadminRequeridoMixin, BusquedaMixin, ListView):
    """El personal de la clínica con buscador y filtros por rol y por estado de la cuenta."""
    template_name = 'cuentas/superadmin/equipo.html'
    context_object_name = 'personas'
    paginate_by = 20

    def get_queryset(self):
        return UsuarioService.personal(self.buscar(), self.request.GET.get('rol', ''), self.request.GET.get('estado', ''))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update({
            'buscar': self.buscar(),
            'rol_elegido': self.request.GET.get('rol', ''),
            'estado_elegido': self.request.GET.get('estado', ''),
            'roles': [(valor, nombre) for valor, nombre in Roles.choices if valor in ROLES_DEL_PERSONAL],
            'estados': [(valor, valor.capitalize()) for valor in ESTADOS_CUENTA],
        })
        return contexto


class EquipoCrearView(SuperadminRequeridoMixin, SuccessMessageMixin, CreateView):
    """Crea la cuenta de un veterinario o de un administrador con una contraseña inicial."""
    form_class = PersonalCreacionForm
    template_name = 'cuentas/superadmin/persona_formulario.html'
    success_url = reverse_lazy('cuentas:equipo')

    def get_initial(self):
        # ?rol=administrador desde el botón "Nuevo administrador"
        rol = self.request.GET.get('rol')
        return {'rol': rol} if rol in (Roles.VETERINARIO, Roles.ADMINISTRADOR) else {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs

    def get_success_message(self, cleaned_data):
        return f'Se creó la cuenta de {self.object} como {self.object.get_rol_display().lower()}.'


class EquipoEditarView(SuperadminRequeridoMixin, CuentaGestionableMixin, SuccessMessageMixin, UpdateView):
    """Datos, rol y estado de una cuenta (el superadministrador también corrige la de un cliente:
    la abre desde Usuarios y vuelve ahí)."""
    form_class = PersonalForm
    template_name = 'cuentas/superadmin/persona_formulario.html'

    def get_success_url(self):
        return reverse('cuentas:usuarios' if self.object.es_cliente else 'cuentas:equipo')

    def get_success_message(self, cleaned_data):
        return f'Se guardaron los cambios de {self.object}.'


class EquipoContrasenaView(SuperadminRequeridoMixin, FormView):
    """Pone una contraseña nueva a una cuenta. Si es la propia, la sesión sigue abierta."""
    form_class = NuevaContrasenaForm
    template_name = 'cuentas/superadmin/contrasena.html'
    success_url = reverse_lazy('cuentas:equipo')

    @cached_property
    def persona(self):
        persona = get_object_or_404(UsuarioService.todas(), pk=self.kwargs['pk'])
        PoliticaDeCuentas.exigir_gestion(self.request.user, persona)
        return persona

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.persona   # SetPasswordForm recibe a quién se le cambia la contraseña
        return kwargs

    def get_context_data(self, **kwargs):
        kwargs['persona'] = self.persona
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        form.save()
        if self.persona.pk == self.request.user.pk:
            update_session_auth_hash(self.request, self.persona)
        messages.success(self.request, f'{self.persona} ya puede entrar con la contraseña nueva.')
        return super().form_valid(form)


class EquipoEstadoView(SuperadminRequeridoMixin, View):
    """Activa o desactiva una cuenta del equipo (POST)."""
    http_method_names = ['post']

    def post(self, request, pk):
        persona = get_object_or_404(UsuarioService.todas(), pk=pk)
        try:
            activa = UsuarioService.alternar_activa(request.user, persona)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            if activa:
                messages.success(request, f'{persona} puede volver a iniciar sesión.')
            else:
                messages.success(request, f'Se desactivó la cuenta de {persona}: ya no puede iniciar sesión.')
        return redirect('cuentas:equipo')
