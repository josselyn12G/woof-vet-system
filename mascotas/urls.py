from django.urls import path

from . import views

app_name = 'mascotas'

urlpatterns = [
    path('', views.MascotaListView.as_view(), name='lista'),
    path('nueva/', views.MascotaCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.MascotaDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.MascotaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.MascotaDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/foto/', views.FotoMascotaView.as_view(), name='foto'),
]
