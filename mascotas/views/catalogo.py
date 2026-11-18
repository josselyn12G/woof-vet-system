"""El catálogo de especies y razas que se ofrece al registrar una mascota (superadministrador)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from cuentas.mixins import SuperadminRequeridoMixin

from ..forms import EspecieForm, RazaForm
from ..mixins import CatalogoFormularioMixin
from ..models import Especie, Raza
from ..services import CatalogoService


class EspecieListView(SuperadminRequeridoMixin, TemplateView):
    """Cada especie con sus razas, cuántas mascotas tiene y sus acciones."""
    template_name = 'mascotas/gestion/especies.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['especies'] = CatalogoService.especies_con_razas()
        return contexto


class EspecieCreateView(CatalogoFormularioMixin, CreateView):
    form_class = EspecieForm
    success_message = 'Se agregó la especie %(nombre)s.'


class EspecieUpdateView(CatalogoFormularioMixin, UpdateView):
    model = Especie
    form_class = EspecieForm
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class RazaCreateView(CatalogoFormularioMixin, CreateView):
    form_class = RazaForm
    success_message = 'Se agregó la raza %(nombre)s.'

    def get_initial(self):
        # ?especie=<id> desde el "Agregar raza" de una especie
        return {'especie': self.request.GET.get('especie')}


class RazaUpdateView(CatalogoFormularioMixin, UpdateView):
    model = Raza
    form_class = RazaForm
    success_message = 'Se guardaron los cambios de %(nombre)s.'


class CatalogoEliminarView(SuperadminRequeridoMixin, View):
    """Borra una especie o una raza (POST). Si alguna mascota la usa no se borra: se ofrece desactivarla."""
    http_method_names = ['post']
    consulta = None   # la función del servicio que da las especies o las razas

    def post(self, request, pk):
        elemento = get_object_or_404(self.consulta(), pk=pk)
        if CatalogoService.eliminar(elemento):
            messages.success(request, f'Se eliminó {elemento}.')
        else:
            messages.error(request, f'{elemento} tiene mascotas registradas y no se puede eliminar. Desactívala en su lugar.')
        return redirect('mascotas:especies')


class EspecieEliminarView(CatalogoEliminarView):
    consulta = staticmethod(CatalogoService.especies)


class RazaEliminarView(CatalogoEliminarView):
    consulta = staticmethod(CatalogoService.razas)
