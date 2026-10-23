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
    # Mi horario: solo el veterinario, y cada uno solo sus bloques (404 con los de otro)
    path('horario/', views.MiHorarioView.as_view(), name='horario'),
    path('horario/<int:pk>/editar/', views.HorarioEditarView.as_view(), name='horario_editar'),
    path('horario/<int:pk>/eliminar/', views.HorarioEliminarView.as_view(), name='horario_eliminar'),
    path('horario/copiar-semana/', views.CopiarSemanaView.as_view(), name='horario_copiar'),
    path('horario/servicios/', views.MisServiciosView.as_view(), name='mis_servicios'),
]
