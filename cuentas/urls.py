from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'cuentas'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('login/', views.LoginDosPasosView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.RegistroView.as_view(), name='registro'),
    path('verificar/', views.VerificarView.as_view(), name='verificar'),
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
