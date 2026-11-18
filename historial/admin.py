from django.contrib import admin

from .models import Consulta, Prescripcion, Vacuna, VacunaAplicada


class PrescripcionInline(admin.TabularInline):
    model = Prescripcion
    extra = 0


class VacunaAplicadaInline(admin.TabularInline):
    model = VacunaAplicada
    extra = 0
    fields = ['vacuna', 'mascota', 'veterinario', 'fecha_aplicacion', 'lote', 'proxima_dosis']


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ['mascota', 'veterinario', 'fecha', 'motivo']
    list_filter = ['veterinario']
    search_fields = ['mascota__nombre', 'motivo', 'diagnostico']
    list_select_related = ['mascota', 'veterinario']
    date_hierarchy = 'fecha'
    raw_id_fields = ['cita']
    inlines = [PrescripcionInline, VacunaAplicadaInline]


@admin.register(Vacuna)
class VacunaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'especie', 'refuerzo_cada_dias', 'activa']
    list_filter = ['activa', 'especie']
    list_editable = ['activa']
    search_fields = ['nombre']


@admin.register(VacunaAplicada)
class VacunaAplicadaAdmin(admin.ModelAdmin):
    list_display = ['mascota', 'vacuna', 'fecha_aplicacion', 'proxima_dosis', 'veterinario']
    list_filter = ['vacuna']
    search_fields = ['mascota__nombre', 'vacuna__nombre', 'lote']
    list_select_related = ['mascota', 'vacuna', 'veterinario']
    date_hierarchy = 'fecha_aplicacion'
    raw_id_fields = ['consulta']
