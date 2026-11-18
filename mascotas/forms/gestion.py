"""La ficha de cualquier mascota, con su dueño (superadministrador)."""
from django import forms

from ..services import MascotaService
from .mis_mascotas import MascotaForm


class DuenoOpcion(forms.ModelChoiceField):
    """En el desplegable se ve el nombre del dueño y su cédula, no su id."""

    def label_from_instance(self, dueno):
        return f'{dueno.get_full_name() or dueno.username} · {dueno.cedula}'


class MascotaGestionForm(MascotaForm):
    """La ficha de una mascota para el superadministrador: los mismos datos que llena el cliente y, además,
    el dueño (solo cuentas de cliente; al editar también se acepta el dueño que ya tiene)."""
    dueno = DuenoOpcion(
        label='Dueño',
        queryset=MascotaService.duenos_posibles().none(),
        empty_label='Elige al dueño',
        error_messages={'required': 'Elige al dueño de la mascota.',
                        'invalid_choice': 'Elige un cliente de la lista.'},
    )

    class Meta(MascotaForm.Meta):
        fields = ['dueno'] + MascotaForm.Meta.fields

    def __init__(self, *args, **kwargs):
        # Sin dueño fijo: el repetido se revisa en clean() con el dueño elegido
        super().__init__(*args, dueno=None, **kwargs)
        self.fields['dueno'].queryset = MascotaService.duenos_posibles(self.instance.dueno_id)

    def clean(self):
        datos = super().clean()
        dueno, nombre = datos.get('dueno'), datos.get('nombre')
        if dueno and nombre and MascotaService.nombre_repetido(dueno, nombre, self.instance.pk):
            self.add_error('nombre', f'{dueno} ya tiene una mascota llamada {nombre}.')
        return datos
