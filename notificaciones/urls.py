from django.urls import path

from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('', views.NotificacionesView.as_view(), name='lista'),
    path('panel/', views.PanelNotificacionesView.as_view(), name='panel'),
]
