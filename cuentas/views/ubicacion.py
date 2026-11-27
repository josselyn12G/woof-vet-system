"""
Las listas de los desplegables dependientes del registro, en JSON (las pide ubicacion.js).

Salen del caché (UbicacionService.opciones_de_*): elegir país y provincia no consulta la base cada vez.
Que la combinación elegida sea válida lo revisa el formulario contra la base (UbicacionService.validar).
"""
from django.http import JsonResponse
from django.views import View

from ..services import UbicacionService


def como_opciones(opciones):
    return JsonResponse({'opciones': opciones})


def id_pedido(request, parametro):
    """El id de ?pais= o ?provincia=; None si viene vacío o inventado (la lista sale vacía)."""
    valor = request.GET.get(parametro, '')
    return int(valor) if valor.isdigit() else None


class ProvinciasView(View):
    """GET ?pais=<id> → las provincias de ese país. Es pública: la usa el registro, antes de tener cuenta."""

    def get(self, request):
        return como_opciones(UbicacionService.opciones_de_provincias(id_pedido(request, 'pais')))


class CiudadesView(View):
    """GET ?provincia=<id> → las ciudades de esa provincia."""

    def get(self, request):
        return como_opciones(UbicacionService.opciones_de_ciudades(id_pedido(request, 'provincia')))
