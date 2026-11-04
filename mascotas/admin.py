from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Especie, Mascota, Raza


class RazaEnLinea(admin.TabularInline):
    model = Raza
    extra = 1


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'plural', 'codigo', 'orden', 'activa']
    list_editable = ['orden', 'activa']
    prepopulated_fields = {'codigo': ['nombre']}
    inlines = [RazaEnLinea]


@admin.register(Raza)
class RazaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'especie', 'activa']
    list_filter = ['especie', 'activa']
    search_fields = ['nombre']
    list_select_related = ['especie']


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'especie', 'raza', 'sexo', 'dueno', 'creado']
    list_filter = ['especie', 'sexo']
    search_fields = ['nombre', 'raza__nombre', 'dueno__username', 'dueno__first_name', 'dueno__last_name']
    list_select_related = ['dueno', 'especie', 'raza']
    readonly_fields = ['vista_foto', 'creado', 'actualizado']

    @admin.display(description='foto')
    def vista_foto(self, mascota):
        if not mascota.foto:
            return 'Sin foto'
        url = reverse('mascotas:foto', args=[mascota.pk])
        return format_html('<img src="{}?v={}" alt="" style="max-height: 200px; border-radius: 12px;">',
                           url, mascota.actualizado.timestamp())
