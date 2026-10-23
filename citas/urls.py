from django.urls import path

from . import views

app_name = 'citas'

urlpatterns = [
    # Catálogo de servicios: solo el administrador (403 para los demás)
    path('servicios/', views.ServicioListView.as_view(), name='servicios'),
    path('servicios/nuevo/', views.ServicioCreateView.as_view(), name='servicio_crear'),
    path('servicios/<int:pk>/editar/', views.ServicioUpdateView.as_view(), name='servicio_editar'),
    path('servicios/<int:pk>/estado/', views.ServicioEstadoView.as_view(), name='servicio_estado'),
    path('servicios/<int:pk>/eliminar/', views.ServicioDeleteView.as_view(), name='servicio_eliminar'),
]
