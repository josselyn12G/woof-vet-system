"""
Mixins de las vistas de citas. Los de acceso por rol están en cuentas/mixins.py; estos los usan como base.

Las mismas vistas de Mi horario sirven al superadministrador para editar el horario de cualquier veterinario
(desde Horarios): solo cambian de quién es el horario, a qué URLs van los formularios y los textos.
"""
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property

from cuentas.mixins import SuperadminRequeridoMixin, VeterinarioRequeridoMixin

from .models import HorarioVeterinario
from .services import CitaService, HorarioService
from .services.formato import plural
from .services.horarios import lunes_de


class HorarioDelVeterinarioMixin(VeterinarioRequeridoMixin):
    """Solo el veterinario entra (403 para los demás) y solo ve sus bloques: el de otro veterinario
    no está en la consulta, así que get_object() responde 404."""
    model = HorarioVeterinario
    # Nombre de cada URL del horario (las de la gestión llevan además el id del veterinario)
    rutas = {'semana': 'citas:horario', 'editar': 'citas:horario_editar', 'eliminar': 'citas:horario_eliminar',
             'copiar': 'citas:horario_copiar', 'servicios': 'citas:mis_servicios'}
    el_horario = 'tu horario'   # para los mensajes: "se cruzaban con tu horario"

    @property
    def veterinario(self):
        return self.request.user

    def url(self, nombre, *args):
        return reverse(self.rutas[nombre], args=args)

    def url_semana(self, fecha):
        return f"{self.url('semana')}?semana={lunes_de(fecha).isoformat()}"

    def texto_servicios(self, cantidad):
        return f'Ahora atiendes {plural(cantidad, "servicio")}.'

    def get_queryset(self):
        return HorarioService.del_veterinario(self.veterinario)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['vet_gestionado'] = None   # la plantilla dice "Mi horario"
        return contexto


class HorarioGestionadoMixin(SuperadminRequeridoMixin):
    """El superadministrador edita el horario del veterinario de la URL (403 para los demás roles;
    404 si el id no es de un veterinario). Un bloque de otro veterinario tampoco está en la consulta."""
    rutas = {'semana': 'citas:gestion_horario', 'editar': 'citas:gestion_horario_editar',
             'eliminar': 'citas:gestion_horario_eliminar', 'copiar': 'citas:gestion_horario_copiar',
             'servicios': 'citas:gestion_horario_servicios'}
    el_horario = 'su horario'

    @cached_property
    def veterinario(self):
        return get_object_or_404(CitaService.veterinarios(), pk=self.kwargs['vet'])

    def url(self, nombre, *args):
        return reverse(self.rutas[nombre], args=[self.veterinario.pk, *args])

    def texto_servicios(self, cantidad):
        return f'{self.veterinario} ahora atiende {plural(cantidad, "servicio")}.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['vet_gestionado'] = self.veterinario
        return contexto
