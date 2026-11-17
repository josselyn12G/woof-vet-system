"""Las listas de los desplegables dependientes del registro, en JSON (las pide ubicacion.js)."""
from django.http import JsonResponse
from django.views import View

from ..services import UbicacionService


def como_opciones(consulta):
    return JsonResponse({'opciones': [{'id': item.pk, 'nombre': item.nombre} for item in consulta]})


def id_pedido(request, parametro):
    """El id de ?pais= o ?provincia=; None si viene vacío o inventado (la lista sale vacía)."""
    valor = request.GET.get(parametro, '')
    return int(valor) if valor.isdigit() else None


class ProvinciasView(View):
    """GET ?pais=<id> → las provincias de ese país. Es pública: la usa el registro, antes de tener cuenta."""

    def get(self, request):
        return como_opciones(UbicacionService.provincias_de(id_pedido(request, 'pais')))


class CiudadesView(View):
    """GET ?provincia=<id> → las ciudades de esa provincia."""

    def get(self, request):
        return como_opciones(UbicacionService.ciudades_de(id_pedido(request, 'provincia')))
