"""El cliente ve la historia clínica y las recetas de sus mascotas desde su menú, eligiendo la mascota."""
from django.views.generic import TemplateView

from cuentas.mixins import ClienteRequeridoMixin
from mascotas.services import MascotaService

from ..services import HistorialService


class MascotasDelClienteMixin(ClienteRequeridoMixin):
    """Las mascotas del cliente y la elegida con ?mascota=<id> (un id ajeno o inventado se ignora)."""

    def mascotas(self):
        return MascotaService.del_dueno(self.request.user).order_by('nombre')

    def elegida(self, mascotas):
        return HistorialService.mascota_elegida(mascotas, self.request.GET.get('mascota'))


class MiHistoriaClinicaView(MascotasDelClienteMixin, TemplateView):
    """
    Historia clínica (menú del cliente): un chip por mascota y la historia de la elegida (la primera si no eligió).
    La línea de tiempo es la misma que la de cada mascota (historial/_historia_columnas.html).
    """
    template_name = 'historial/cliente/mi_historia.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        mascotas = self.mascotas()
        mascota = self.elegida(mascotas) or mascotas.first()
        contexto.update({'mascotas': mascotas, 'mascota': mascota})
        if mascota is not None:
            contexto.update(HistorialService.de_la_mascota(mascota))
            contexto.update(HistorialService.tablero(mascota, contexto['consultas']))
        return contexto


class MisRecetasView(MascotasDelClienteMixin, TemplateView):
    """Mis recetas: todas las de sus mascotas agrupadas por mascota, o solo las de una (?mascota=<id>)."""
    template_name = 'historial/cliente/mis_recetas.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        mascotas = self.mascotas()
        elegida = self.elegida(mascotas)
        por_mascota = HistorialService.recetas_del_cliente(self.request.user, elegida)
        contexto.update({
            'mascotas': mascotas,
            'mascota_elegida': elegida,
            'por_mascota': por_mascota,
            'en_curso': sum(1 for _, recetas in por_mascota for receta in recetas if receta.en_curso),
        })
        return contexto
