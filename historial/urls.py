from django.urls import path

from . import views

app_name = 'historial'

urlpatterns = [
    # RF-20: el veterinario registra la consulta de una cita atendida suya (404 con la de otro)
    path('citas/<int:pk>/consulta/', views.RegistrarConsultaView.as_view(), name='consulta'),
]
