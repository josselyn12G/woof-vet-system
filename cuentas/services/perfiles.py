"""El perfil del veterinario: dónde se busca y qué cuenta como veterinario verificado."""
from django.db.models import Q

from cuentas.models import PerfilVeterinario

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
