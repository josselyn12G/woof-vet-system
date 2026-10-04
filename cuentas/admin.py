from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Woof', {'fields': ('rol', 'telefono', 'sector',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Woof', {'fields': ('rol', 'telefono', 'email',)}),
    )
    list_display = ['username', 'email', 'first_name', 'last_name', 'rol', 'is_staff']
    list_filter = UserAdmin.list_filter + ('rol',)
    search_fields = ['username', 'first_name', 'last_name', 'email', 'telefono']	