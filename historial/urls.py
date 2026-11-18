from django.urls import path

from . import views

app_name = 'historial'

urlpatterns = [
    # RF-20: el veterinario registra la consulta de una cita atendida suya (404 con la de otro)
    path('citas/<int:pk>/consulta/', views.RegistrarConsultaView.as_view(), name='consulta'),
    # Menú del cliente: la historia clínica y las recetas de sus mascotas (403 para los demás roles)
    path('mi-historia/', views.MiHistoriaClinicaView.as_view(), name='mi_historia'),
    path('mis-recetas/', views.MisRecetasView.as_view(), name='mis_recetas'),
    path('mis-recetas/consulta/<int:pk>/', views.TratamientoView.as_view(), name='tratamiento'),
    # El check de cada día del tratamiento (POST, solo recetas de sus mascotas: 404 con las de otro)
    path('mis-recetas/<int:pk>/marcar/', views.MarcarDiaView.as_view(), name='marcar_dia'),
    # Al cerrar el pop-up de un medicamento: todos los días marcados en un solo POST
    path('mis-recetas/<int:pk>/dias/', views.GuardarDiasView.as_view(), name='guardar_dias'),
    # Catálogo de vacunas: administrador y superadministrador (403 para los demás)
    path('vacunas/', views.VacunaListView.as_view(), name='vacunas'),
    path('vacunas/nueva/', views.VacunaCreateView.as_view(), name='vacuna_crear'),
    path('vacunas/<int:pk>/editar/', views.VacunaUpdateView.as_view(), name='vacuna_editar'),
    path('vacunas/<int:pk>/estado/', views.VacunaEstadoView.as_view(), name='vacuna_estado'),
]
