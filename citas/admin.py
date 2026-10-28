from django.contrib import admin

from .models import HorarioVeterinario, Servicio


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
