import csv

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from citas.services.horarios import semana_pedida
from cuentas.forms import (
    NuevaContrasenaForm, PersonalCreacionForm, PersonalForm, RegistroForm, UsuarioRolForm, VerificarCodigoForm,
)
from cuentas.mixins import (
    AdministradorRequeridoMixin, ClienteRequeridoMixin, SuperadminRequeridoMixin, VeterinarioRequeridoMixin,
)
from cuentas.models import ROLES_DEL_PERSONAL, Roles
from cuentas.services import (
    PoliticaDeCuentas, UsuarioService, cancelar_login_pendiente, enviar_codigo, hay_login_pendiente, verificar_codigo,
)
from cuentas.services.estadisticas import (
    PERIODOS_ADMINISTRADOR, PERIODOS_VETERINARIO, PanelAdministradorService, PanelClienteService,
    PanelSuperadminService, PanelVeterinarioService, elegir_periodo, opciones_de_periodo,
)
from cuentas.services.usuarios import ESTADOS_CUENTA


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'


class InicioClienteView(ClienteRequeridoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_cliente.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelClienteService.resumen(self.request.user))
        return contexto


class PeriodoMixin:
    """Lee ?periodo= (un valor inventado vuelve al de siempre) y lo deja en el contexto para los segmentos."""
    periodos = {}
    periodo_por_defecto = ''

    def periodo(self):
        return elegir_periodo(self.request.GET.get('periodo', self.periodo_por_defecto), self.periodos,
                              self.periodo_por_defecto)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['periodos'] = opciones_de_periodo(self.periodos)
        contexto['periodo'] = self.periodo()[0]
        return contexto


class InicioVeterinarioView(VeterinarioRequeridoMixin, PeriodoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_veterinario.html'
    periodos = PERIODOS_VETERINARIO
    periodo_por_defecto = '7d'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # ?semana= mueve "Mi semana" a otra semana (cualquier día sirve; una fecha inventada vuelve a la actual)
        lunes = semana_pedida(self.request.GET.get('semana'))
        contexto.update(PanelVeterinarioService.resumen(self.request.user, self.periodo()[1], lunes))
        return contexto


class InicioAdministradorView(AdministradorRequeridoMixin, PeriodoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_administrador.html'
    periodos = PERIODOS_ADMINISTRADOR
    periodo_por_defecto = 'mes'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelAdministradorService.resumen(self.periodo()[1]))
        return contexto


class ReporteUsuariosView(AdministradorRequeridoMixin, View):
    """Descarga las cuentas en CSV (sin contraseñas): lo que hace el botón "Descargar reporte"."""

    def get(self, request):
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = f'attachment; filename="woof-cuentas-{timezone.localdate():%Y-%m-%d}.csv"'
        respuesta.write('﻿')   # para que Excel lea bien las tildes
        csv.writer(respuesta).writerows(UsuarioService.filas_del_reporte())
        return respuesta


class BusquedaMixin:
    def buscar(self):
        return self.request.GET.get('q', '').strip()


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


class CuentaGestionableMixin:
    """La cuenta de la URL, solo si quien la abre puede gestionarla (si no, 403). El formulario recibe al actor."""
    context_object_name = 'persona'

    def get_queryset(self):
        return get_user_model().objects.all()

    def get_object(self, queryset=None):
        persona = super().get_object(queryset)
        if not PoliticaDeCuentas.puede_gestionar(self.request.user, persona):
            raise PermissionDenied
        return persona

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs


class UsuarioEditarView(AdministradorRequeridoMixin, CuentaGestionableMixin, SuccessMessageMixin, UpdateView):
    """Cambiar el rol de una cuenta (por ejemplo, darle el rol de veterinario) o desactivarla."""
    form_class = UsuarioRolForm
    template_name = 'cuentas/panel/usuario_editar.html'
    success_url = reverse_lazy('cuentas:usuarios')
    success_message = 'Se guardaron los cambios de %(persona)s.'

    def get_success_message(self, cleaned_data):
        return self.success_message % {'persona': self.object}


class PanelView(LoginRequiredMixin, View):
    """Después del login, manda a cada usuario a la portada de su rol. No dibuja nada: solo redirige."""

    def get(self, request):
        if request.user.es_veterinario:
            return redirect('cuentas:inicio_veterinario')
        if request.user.es_superadmin:
            return redirect('cuentas:inicio_superadmin')
        if request.user.es_administrador:
            return redirect('cuentas:inicio_administrador')
        return redirect('cuentas:inicio_cliente')  # el cliente es el rol por defecto


# ---------------------------------------------------------------------------
# Superadministrador: gestiona al equipo de la clínica (administradores y veterinarios)
# ---------------------------------------------------------------------------
class InicioSuperadminView(SuperadminRequeridoMixin, TemplateView):
    template_name = 'cuentas/superadmin/inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(PanelSuperadminService.resumen())
        return contexto


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
        persona = get_object_or_404(get_user_model(), pk=self.kwargs['pk'])
        if not PoliticaDeCuentas.puede_gestionar(self.request.user, persona):
            raise PermissionDenied
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
        persona = get_object_or_404(get_user_model(), pk=pk)
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


# ---------------------------------------------------------------------------
# Registro e inicio de sesión
# ---------------------------------------------------------------------------
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

        usuario = self.usuario_que_entra
        self.request.session['pre_2fa_user'] = usuario.pk           # la sesión es JSON: se guarda el pk, no el objeto
        self.request.session['pre_2fa_next'] = self.get_success_url()  # a dónde ir al terminar (respeta ?next=)
        enviar_codigo(self.request, usuario)
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

        # Se sacan de la sesión antes del login(), que cambia la llave de la sesión por seguridad
        pk = self.request.session.pop('pre_2fa_user')
        siguiente = self.request.session.pop('pre_2fa_next', '/')

        usuario = get_user_model().objects.get(pk=pk)
        login(self.request, usuario)
        return redirect(siguiente)
