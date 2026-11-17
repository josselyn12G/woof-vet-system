from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Ciudad, Pais, PerfilVeterinario, Provincia, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Woof', {'fields': ('rol', 'telefono', 'sector', 'cedula', 'ciudad')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Woof', {'fields': ('rol', 'telefono', 'email', 'cedula')}),
    )
    list_display = ['username', 'email', 'first_name', 'last_name', 'rol', 'is_staff']
    list_filter = UserAdmin.list_filter + ('rol',)
    search_fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'cedula']


@admin.register(PerfilVeterinario)
class PerfilVeterinarioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'especialidad', 'anios_experiencia', 'verificado']
    list_filter = ['verificado']
    search_fields = ['usuario__first_name', 'usuario__last_name', 'usuario__username', 'especialidad']


class ProvinciaInline(admin.TabularInline):
    model = Provincia
    extra = 0


class CiudadInline(admin.TabularInline):
    model = Ciudad
    extra = 0


@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    search_fields = ['nombre']
    inlines = [ProvinciaInline]


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'pais']
    list_filter = ['pais']
    search_fields = ['nombre']
    inlines = [CiudadInline]


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'provincia']
    list_filter = ['provincia__pais', 'provincia']
    search_fields = ['nombre', 'provincia__nombre']
    list_select_related = ['provincia']
