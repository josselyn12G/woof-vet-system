from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Mascota


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'especie', 'raza', 'sexo', 'dueno', 'creado']
    list_filter = ['especie', 'sexo']
    search_fields = ['nombre', 'raza', 'dueno__username', 'dueno__first_name', 'dueno__last_name']
    list_select_related = ['dueno']
    readonly_fields = ['vista_foto', 'creado', 'actualizado']

    @admin.display(description='foto')
    def vista_foto(self, mascota):
        if not mascota.foto:
            return 'Sin foto'
        url = reverse('mascotas:foto', args=[mascota.pk])
        return format_html('<img src="{}?v={}" alt="" style="max-height: 200px; border-radius: 12px;">',
                           url, mascota.actualizado.timestamp())
