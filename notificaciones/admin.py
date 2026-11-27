from django.contrib import admin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'cita', 'vacuna_aplicada', 'creado', 'leida', 'correo_enviado', 'intentos_correo']
    list_filter = ['tipo', 'leida', 'correo_enviado']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'mensaje']
    list_select_related = ['usuario', 'cita', 'cita__mascota', 'vacuna_aplicada__vacuna', 'vacuna_aplicada__mascota']
