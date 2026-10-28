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
    # Core: el cliente agenda y ve sus citas (403 para los demás roles)
    path('agendar/', views.AgendarCitaView.as_view(), name='agendar'),
    path('agendar/turnos/', views.TurnosDelDiaView.as_view(), name='turnos_del_dia'),
    path('agendar/dias/', views.DiasDisponiblesView.as_view(), name='dias_disponibles'),
    path('mis-citas/', views.MisCitasView.as_view(), name='mis_citas'),
    path('mis-citas/<int:pk>/cancelar/', views.CancelarCitaView.as_view(), name='cancelar'),
    # Core: la agenda del veterinario (solo sus citas)
    path('agenda/', views.AgendaVeterinarioView.as_view(), name='agenda'),
    path('agenda/<int:pk>/resultado/', views.ResultadoCitaView.as_view(), name='resultado'),
    path('pacientes/', views.PacientesView.as_view(), name='pacientes'),
]
