from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .forms import RecuperarContrasenaForm

app_name = 'cuentas'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('login/', views.LoginDosPasosView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.RegistroView.as_view(), name='registro'),
    path('verificar/', views.VerificarView.as_view(), name='verificar'),
    # HU-23 y HU-13: los términos y el enlace que verifica el correo (públicos)
    path('terminos/', views.TerminosView.as_view(), name='terminos'),
    path('correo/verificar/<uidb64>/<token>/', views.VerificarCorreoView.as_view(), name='verificar_correo'),
    # HU-14: recuperar la contraseña con un enlace por correo (vistas de Django, plantillas y correo de Woof)
    path('contrasena/recuperar/', auth_views.PasswordResetView.as_view(
        form_class=RecuperarContrasenaForm, template_name='cuentas/acceso/recuperar.html',
        success_url=reverse_lazy('cuentas:recuperar_enviado'),
    ), name='recuperar_contrasena'),
    path('contrasena/recuperar/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='cuentas/acceso/recuperar_enviado.html',
    ), name='recuperar_enviado'),
    path('contrasena/nueva/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='cuentas/acceso/contrasena_nueva.html', success_url=reverse_lazy('cuentas:contrasena_lista'),
    ), name='contrasena_nueva'),
    path('contrasena/nueva/lista/', auth_views.PasswordResetCompleteView.as_view(
        template_name='cuentas/acceso/contrasena_lista.html',
    ), name='contrasena_lista'),
    # HU-22 y HU-21: Mi cuenta (cualquier rol con sesión)
    path('panel/mi-cuenta/', views.MiCuentaView.as_view(), name='mi_cuenta'),
    path('panel/mi-cuenta/contrasena/', views.CambiarContrasenaView.as_view(), name='cambiar_contrasena'),
    path('panel/mi-cuenta/verificar-correo/', views.ReenviarVerificacionView.as_view(), name='reenviar_verificacion'),
    # Desplegables dependientes del registro: país → provincia → ciudad (JSON, públicas)
    path('ubicacion/provincias/', views.ProvinciasView.as_view(), name='provincias'),
    path('ubicacion/ciudades/', views.CiudadesView.as_view(), name='ciudades'),
    # Gestión de usuarios del administrador (las portadas de cada rol están en la app panel)
    path('panel/administrador/usuarios/', views.UsuarioListView.as_view(), name='usuarios'),
    path('panel/administrador/reporte.csv', views.ReporteUsuariosView.as_view(), name='reporte_usuarios'),
    path('panel/administrador/usuarios/<int:pk>/', views.UsuarioEditarView.as_view(), name='usuario_editar'),
    # Superadministrador: el equipo de la clínica (403 para los demás roles)
    path('panel/superadmin/equipo/', views.EquipoListView.as_view(), name='equipo'),
    path('panel/superadmin/equipo/nuevo/', views.EquipoCrearView.as_view(), name='equipo_crear'),
    path('panel/superadmin/equipo/<int:pk>/', views.EquipoEditarView.as_view(), name='equipo_editar'),
    path('panel/superadmin/equipo/<int:pk>/contrasena/', views.EquipoContrasenaView.as_view(), name='equipo_contrasena'),
    path('panel/superadmin/equipo/<int:pk>/estado/', views.EquipoEstadoView.as_view(), name='equipo_estado'),
]
