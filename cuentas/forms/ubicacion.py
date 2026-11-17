"""País → provincia → ciudad en un formulario: el registro y Mi cuenta usan la misma lógica."""
from django import forms
from django.core.exceptions import ValidationError

from ..services.ubicacion import UbicacionService


def id_valido(valor):
    return valor if str(valor or '').isdigit() else None


class UbicacionMixin:
    """
    Para un ModelForm del Usuario que tiene el campo 'ciudad'. Agrega los desplegables de país y provincia
    (no son campos del modelo) y filtra cada lista por lo elegido antes: lo enviado o, al abrir, lo inicial.
    ubicacion.js los llena con las vistas JSON; el servidor vuelve a revisar que encajen (UbicacionService.validar).
    """

    def preparar_ubicacion(self, pais=None, provincia=None):
        if self.is_bound:
            pais, provincia = self.data.get('pais'), self.data.get('provincia')
        else:
            self.initial.setdefault('pais', pais)
            self.initial.setdefault('provincia', provincia)

        campos = {
            'pais': forms.ModelChoiceField(
                label='País', queryset=UbicacionService.paises(), empty_label='Elige tu país',
                error_messages={'required': 'Elige tu país.'},
            ),
            'provincia': forms.ModelChoiceField(
                label='Provincia', queryset=UbicacionService.provincias_de(id_valido(pais)),
                empty_label='Elige tu provincia',
                error_messages={'required': 'Elige tu provincia.', 'invalid_choice': 'Elige una provincia de la lista.'},
            ),
        }
        # País y provincia van justo antes de la ciudad
        ordenados = {}
        for nombre, campo in self.fields.items():
            if nombre == 'ciudad':
                ordenados.update(campos)
            ordenados[nombre] = campo
        self.fields = ordenados

        ciudad = self.fields['ciudad']
        ciudad.required = True   # opcional en el modelo (cuentas antiguas), obligatoria en el formulario
        ciudad.empty_label = 'Elige tu ciudad'
        ciudad.error_messages.update({'required': 'Elige tu ciudad.', 'invalid_choice': 'Elige una ciudad de la lista.'})
        ciudad.queryset = UbicacionService.ciudades_de(id_valido(provincia))
        for nombre in ('pais', 'provincia', 'ciudad'):
            self.fields[nombre].widget.attrs['data-ubicacion'] = nombre

    def validar_ubicacion(self, datos):
        pais, provincia, ciudad = datos.get('pais'), datos.get('provincia'), datos.get('ciudad')
        if pais and provincia and ciudad:
            try:
                UbicacionService.validar(pais, provincia, ciudad)
            except ValidationError as error:
                # El service dice en qué campo está el problema (provincia o ciudad): el error sale debajo de él
                for campo, mensajes in error.message_dict.items():
                    self.add_error(campo, mensajes)
