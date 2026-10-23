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
    # Panel: /panel/ redirige a la portada del rol; cada portada solo la abre su rol (403 para los demás)
    path('panel/', views.PanelView.as_view(), name='panel'),
    path('panel/cliente/', views.InicioClienteView.as_view(), name='inicio_cliente'),
    path('panel/veterinario/', views.InicioVeterinarioView.as_view(), name='inicio_veterinario'),
    path('panel/administrador/', views.InicioAdministradorView.as_view(), name='inicio_administrador'),
    path('panel/administrador/usuarios/', views.UsuarioListView.as_view(), name='usuarios'),
    path('panel/administrador/reporte.csv', views.ReporteUsuariosView.as_view(), name='reporte_usuarios'),
    path('panel/administrador/usuarios/<int:pk>/', views.UsuarioEditarView.as_view(), name='usuario_editar'),
]
