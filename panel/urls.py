from django.urls import path

from . import views

app_name = 'panel'

# Se incluye en /panel/: /panel/ redirige a la portada del rol; cada portada solo la abre su rol (403 para los demás)
urlpatterns = [
    path('', views.PanelView.as_view(), name='panel'),
    path('cliente/', views.InicioClienteView.as_view(), name='inicio_cliente'),
    path('veterinario/', views.InicioVeterinarioView.as_view(), name='inicio_veterinario'),
    path('administrador/', views.InicioAdministradorView.as_view(), name='inicio_administrador'),
    path('superadmin/', views.InicioSuperadminView.as_view(), name='inicio_superadmin'),
]
