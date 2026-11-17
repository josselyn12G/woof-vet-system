from django.urls import path

from . import views

app_name = 'historial'

urlpatterns = [
    # RF-20: el veterinario registra la consulta de una cita atendida suya (404 con la de otro)
    path('citas/<int:pk>/consulta/', views.RegistrarConsultaView.as_view(), name='consulta'),
    # Catálogo de vacunas: administrador y superadministrador (403 para los demás)
    path('vacunas/', views.VacunaListView.as_view(), name='vacunas'),
    path('vacunas/nueva/', views.VacunaCreateView.as_view(), name='vacuna_crear'),
    path('vacunas/<int:pk>/editar/', views.VacunaUpdateView.as_view(), name='vacuna_editar'),
    path('vacunas/<int:pk>/estado/', views.VacunaEstadoView.as_view(), name='vacuna_estado'),
]
