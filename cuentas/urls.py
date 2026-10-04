from django.urls import path
from . import views

app_name = 'cuentas'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
]
