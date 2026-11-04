from django.db.models import ProtectedError, Q

from citas.models import Servicio

# Filtro de estado del catálogo: valor en la URL -> condición
ESTADOS_SERVICIO = {'activos': True, 'inactivos': False}


class ServicioService:
    """El catálogo de servicios de la clínica (HU-25, RF-04 a RF-06)."""

    @staticmethod
    def buscar(texto='', estado=''):
        servicios = Servicio.objects.prefetch_related('veterinarios')
        if texto:
            servicios = servicios.filter(Q(nombre__icontains=texto) | Q(descripcion__icontains=texto))
        if estado in ESTADOS_SERVICIO:  # un estado inventado en la URL se ignora
            servicios = servicios.filter(activo=ESTADOS_SERVICIO[estado])
        return servicios

    @staticmethod
    def alternar_estado(servicio):
        """Activa o desactiva el servicio y devuelve cómo quedó."""
        servicio.activo = not servicio.activo
        servicio.save(update_fields=['activo'])
        return servicio.activo

    @staticmethod
    def eliminar(servicio):
        """Borra el servicio. Devuelve False si tiene citas (Cita.servicio es PROTECT): ese se desactiva, no se borra."""
        try:
            servicio.delete()
        except ProtectedError:
            return False
        return True

    @staticmethod
    def todos():
        return Servicio.objects.all()

    @staticmethod
    def activos():
        """Los que se ofrecen hoy: las casillas de "Servicios que atiendo"."""
        return Servicio.objects.filter(activo=True)

    @staticmethod
    def activo(pk):
        """El servicio activo con ese id (llega en la URL), o None si no existe, está inactivo o el id es inventado."""
        if not str(pk or '').isdigit():
            return None
        return Servicio.objects.filter(pk=pk, activo=True).first()

    @staticmethod
    def nombre_repetido(nombre, excluir_pk=None):
        """True si otro servicio ya se llama así: "Vacunación" y "vacunación" son el mismo."""
        return Servicio.objects.filter(nombre__iexact=nombre).exclude(pk=excluir_pk).exists()

    @staticmethod
    def lo_atiende(servicio, veterinario):
        return servicio.veterinarios.filter(pk=veterinario.pk).exists()

    @staticmethod
    def agendables():
        """Servicios activos que algún veterinario atiende: los únicos que el cliente puede agendar."""
        return Servicio.objects.filter(activo=True, veterinarios__isnull=False).distinct()
