"""El perfil del veterinario: dónde se busca y qué cuenta como veterinario verificado."""
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Q

from cuentas.models import PerfilVeterinario, Roles

# Filtro para consultas de usuarios: solo los veterinarios que el administrador ya verificó
VERIFICADO = Q(perfil_veterinario__verificado=True)


class PerfilVeterinarioService:

    @staticmethod
    def de(veterinario):
        """El perfil del veterinario; si todavía no tiene, uno nuevo sin guardar (sin verificar)."""
        return PerfilVeterinario.objects.filter(usuario=veterinario).first() or PerfilVeterinario(usuario=veterinario)

    @staticmethod
    def esta_verificado(veterinario):
        return PerfilVeterinario.objects.filter(usuario=veterinario, verificado=True).exists()

    @staticmethod
    def destacados(cantidad=3):
        """
        Los veterinarios de la portada: activos y verificados, con su calificación promedio y cuántas opiniones
        tienen; primero los mejor calificados (los que aún no tienen opiniones van al final).
        """
        return list(
            get_user_model().objects.filter(VERIFICADO, rol=Roles.VETERINARIO, is_active=True)
            .select_related('perfil_veterinario')
            .annotate(promedio=Avg('citas_atendidas__calificacion__estrellas'),
                      opiniones=Count('citas_atendidas__calificacion'))
            .order_by(F('promedio').desc(nulls_last=True), 'first_name', 'last_name')[:cantidad]
        )
