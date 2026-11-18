from django.urls import path

from historial.views import HistoriaClinicaView, MisHistorialesView

from . import views

app_name = 'mascotas'

urlpatterns = [
    path('', views.MascotaListView.as_view(), name='lista'),
    # «Historial médico» del sidebar del cliente: sus mascotas con sus tratamientos en curso
    path('historiales/', MisHistorialesView.as_view(), name='historiales'),
    path('nueva/', views.MascotaCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.MascotaDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.MascotaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.MascotaDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/carnet/', views.MascotaCarnetView.as_view(), name='carnet'),
    # Historia clínica de solo lectura: el dueño (404 con una ajena), los veterinarios y la clínica
    path('<int:pk>/historial/', HistoriaClinicaView.as_view(), name='historial'),
    path('<int:pk>/foto/', views.FotoMascotaView.as_view(), name='foto'),
    # Gestión de la clínica: administrador y superadministrador (403 para los demás)
    path('gestion/', views.MascotaGestionListView.as_view(), name='gestion'),
    path('gestion/<int:pk>/', views.MascotaGestionDetailView.as_view(), name='gestion_detalle'),
    # Crear, editar y eliminar cualquier ficha: solo el superadministrador (403 para los demás)
    path('gestion/nueva/', views.MascotaGestionCreateView.as_view(), name='gestion_crear'),
    path('gestion/<int:pk>/editar/', views.MascotaGestionUpdateView.as_view(), name='gestion_editar'),
    path('gestion/<int:pk>/eliminar/', views.MascotaGestionDeleteView.as_view(), name='gestion_eliminar'),
    # Catálogo de especies y razas: solo el superadministrador (403 para los demás)
    path('especies/', views.EspecieListView.as_view(), name='especies'),
    path('especies/nueva/', views.EspecieCreateView.as_view(), name='especie_crear'),
    path('especies/<int:pk>/editar/', views.EspecieUpdateView.as_view(), name='especie_editar'),
    path('especies/<int:pk>/eliminar/', views.EspecieEliminarView.as_view(), name='especie_eliminar'),
    path('razas/nueva/', views.RazaCreateView.as_view(), name='raza_crear'),
    path('razas/<int:pk>/editar/', views.RazaUpdateView.as_view(), name='raza_editar'),
    path('razas/<int:pk>/eliminar/', views.RazaEliminarView.as_view(), name='raza_eliminar'),
]
