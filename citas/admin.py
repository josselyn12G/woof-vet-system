from django.contrib import admin

from .models import Calificacion, HorarioVeterinario, Notificacion, Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'duracion_min', 'precio', 'activo']
    list_filter = ['activo']
    list_editable = ['activo']
    search_fields = ['nombre', 'descripcion']
    filter_horizontal = ['veterinarios']


@admin.register(HorarioVeterinario)
class HorarioVeterinarioAdmin(admin.ModelAdmin):
    list_display = ['veterinario', 'fecha', 'hora_inicio', 'hora_fin']
    list_filter = ['fecha', 'veterinario']
    search_fields = ['veterinario__username', 'veterinario__first_name', 'veterinario__last_name']
    list_select_related = ['veterinario']
    date_hierarchy = 'fecha'


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ['cita', 'estrellas', 'creado']
    list_filter = ['estrellas']
    search_fields = ['cita__mascota__nombre', 'cita__veterinario__first_name', 'cita__veterinario__last_name']
    list_select_related = ['cita', 'cita__mascota']


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'cita', 'vacuna_aplicada', 'creado', 'leida']
    list_filter = ['tipo', 'leida']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'mensaje']
    list_select_related = ['usuario', 'cita', 'cita__mascota', 'vacuna_aplicada__vacuna', 'vacuna_aplicada__mascota']
