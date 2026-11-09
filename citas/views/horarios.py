"""Mi horario del veterinario (HU-26, RF-07 a RF-10) y las mismas pantallas para el superadministrador."""
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views import View
from django.views.generic import CreateView, DeleteView, UpdateView

from ..forms import HorarioForm, MisServiciosForm
from ..mixins import HorarioDelVeterinarioMixin, HorarioGestionadoMixin
from ..models import HorarioVeterinario
from ..services import HorarioService
from ..services.formato import plural
from ..services.horarios import leer_fecha, semana_pedida


class MiHorarioView(HorarioDelVeterinarioMixin, SuccessMessageMixin, CreateView):
    """La semana en columnas (un día por columna), el formulario "Nuevo bloque" y los servicios que atiende."""
    form_class = HorarioForm
    template_name = 'citas/horario/semana.html'
    success_message = 'Se agregó el bloque del %(fecha)s de %(hora_inicio)s a %(hora_fin)s.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # El veterinario no va en el formulario (es el de la sesión o el de la URL); va antes de validar
        # para revisar los cruces
        kwargs['instance'] = HorarioVeterinario(veterinario=self.veterinario)
        return kwargs

    def get_initial(self):
        # ?fecha= llega desde el "+" de un día de la grilla; si no, hoy o el lunes de la semana elegida
        lunes = semana_pedida(self.request.GET.get('semana'))
        return {'fecha': HorarioService.fecha_sugerida(lunes, leer_fecha(self.request.GET.get('fecha')))}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        lunes = semana_pedida(self.request.GET.get('semana'))
        contexto.update(HorarioService.semana_del_veterinario(self.veterinario, lunes))
        for dia in contexto['dias']:
            for bloque in dia['bloques']:
                bloque.url_editar = self.url('editar', bloque.pk)
                bloque.url_eliminar = self.url('eliminar', bloque.pk)
        contexto['rutas'] = {nombre: self.url(nombre) for nombre in ('semana', 'copiar', 'servicios')}
        contexto['servicios_form'] = MisServiciosForm(
            initial={'servicios': HorarioService.servicios_activos(self.veterinario)},
        )
        return contexto

    def get_success_message(self, cleaned_data):
        return self.success_message % {
            'fecha': cleaned_data['fecha'].strftime('%d/%m'),
            'hora_inicio': cleaned_data['hora_inicio'].strftime('%H:%M'),
            'hora_fin': cleaned_data['hora_fin'].strftime('%H:%M'),
        }

    def get_success_url(self):
        return self.url_semana(self.object.fecha)


class HorarioEditarView(HorarioDelVeterinarioMixin, SuccessMessageMixin, UpdateView):
    form_class = HorarioForm
    template_name = 'citas/horario/editar.html'
    context_object_name = 'bloque'
    success_message = 'Se guardaron los cambios del bloque.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Con errores, self.object trae la fecha que se escribió: "Cancelar" vuelve a la semana guardada
        contexto['volver'] = self.url_semana(HorarioService.fecha_guardada(self.object))
        return contexto

    def get_success_url(self):
        return self.url_semana(self.object.fecha)


class HorarioEliminarView(HorarioDelVeterinarioMixin, DeleteView):
    """Solo POST (el botón pide confirmación en el navegador). Cuando exista Cita, aquí se debe impedir
    quitar un bloque que ya tiene citas reservadas (HU-26)."""
    http_method_names = ['post']

    def form_valid(self, form):
        fecha = HorarioService.quitar_bloque(self.object)
        messages.success(self.request, f'Se quitó el bloque de {self.el_horario}.')
        return redirect(self.url_semana(fecha))


class CopiarSemanaView(HorarioDelVeterinarioMixin, View):
    """Copia los bloques de la semana anterior en la semana elegida (HU-26). Se saltan los días que ya
    pasaron y los bloques que se cruzarían con otros que ya están cargados."""
    http_method_names = ['post']

    def post(self, request, **kwargs):
        lunes = semana_pedida(request.POST.get('semana'))
        try:
            copiados, omitidos = HorarioService.copiar_semana(self.veterinario, lunes)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect(self.url_semana(lunes))

        if copiados:
            texto = f'Se copiaron {plural(copiados, "bloque")} de la semana anterior.'
            if omitidos:
                texto += f' {omitidos} no se copiaron porque el día ya pasó o se cruzaban con {self.el_horario}.'
            messages.success(request, texto)
        else:
            messages.error(request,
                           f'No se copió ningún bloque: los días ya pasaron o se cruzaban con {self.el_horario}.')
        return redirect(self.url_semana(lunes))


class MisServiciosView(HorarioDelVeterinarioMixin, View):
    """Guarda los servicios que atiende el veterinario: solo aparece al agendar los que marque."""
    http_method_names = ['post']

    def post(self, request, **kwargs):
        formulario = MisServiciosForm(request.POST)
        destino = self.url_semana(semana_pedida(request.POST.get('semana')))
        if not formulario.is_valid():
            messages.error(request, 'Elige servicios de la lista.')
            return redirect(destino)
        cantidad = HorarioService.guardar_servicios(self.veterinario, formulario.cleaned_data['servicios'])
        messages.success(request, self.texto_servicios(cantidad))
        return redirect(destino)


# El superadministrador, en el horario de un veterinario (Horarios > el veterinario)
class GestionHorarioView(HorarioGestionadoMixin, MiHorarioView):
    pass


class GestionHorarioEditarView(HorarioGestionadoMixin, HorarioEditarView):
    pass


class GestionHorarioEliminarView(HorarioGestionadoMixin, HorarioEliminarView):
    pass


class GestionCopiarSemanaView(HorarioGestionadoMixin, CopiarSemanaView):
    pass


class GestionServiciosVeterinarioView(HorarioGestionadoMixin, MisServiciosView):
    pass
