"""Entrar a Woof: el registro y el código de 6 dígitos del login en dos pasos."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from ..models import Provincia, Usuario
from ..services.ubicacion import UbicacionService
from .comunes import ETIQUETAS


class RegistroForm(UserCreationForm):
    """
    El registro del cliente. País → provincia → ciudad son desplegables dependientes: ubicacion.js los llena
    con las vistas JSON, y el servidor vuelve a revisar que encajen (UbicacionService.validar).
    Sin JavaScript también funciona: país y provincia se envían y la página vuelve con las listas filtradas.
    """
    pais = forms.ModelChoiceField(label='País', queryset=UbicacionService.paises(), empty_label='Elige tu país',
                                  error_messages={'required': 'Elige tu país.'})
    provincia = forms.ModelChoiceField(label='Provincia', queryset=Provincia.objects.none(),
                                       empty_label='Elige tu provincia',
                                       error_messages={'required': 'Elige tu provincia.',
                                                       'invalid_choice': 'Elige una provincia de la lista.'})

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'cedula', 'ciudad']
        labels = {campo: ETIQUETAS[campo] for campo in fields}
        widgets = {
            'cedula': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 10, 'placeholder': 'Tus 10 números'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La ciudad es opcional en el modelo (cuentas antiguas), pero quien se registra la tiene que elegir
        self.fields['ciudad'].required = True
        self.fields['ciudad'].empty_label = 'Elige tu ciudad'
        self.fields['ciudad'].error_messages.update({'required': 'Elige tu ciudad.',
                                                     'invalid_choice': 'Elige una ciudad de la lista.'})
        for nombre, rol in (('pais', 'pais'), ('provincia', 'provincia'), ('ciudad', 'ciudad')):
            self.fields[nombre].widget.attrs['data-ubicacion'] = rol

        # Cada lista se filtra por lo elegido antes (lo enviado o, al abrir, Ecuador)
        pais = self.data.get('pais') if self.is_bound else getattr(UbicacionService.pais_por_defecto(), 'pk', None)
        provincia = self.data.get('provincia') if self.is_bound else None
        if not self.is_bound and pais:
            self.initial.setdefault('pais', pais)
        self.fields['provincia'].queryset = UbicacionService.provincias_de(pais if str(pais or '').isdigit() else None)
        self.fields['ciudad'].queryset = UbicacionService.ciudades_de(
            provincia if str(provincia or '').isdigit() else None
        )

    def clean(self):
        datos = super().clean()
        pais, provincia, ciudad = datos.get('pais'), datos.get('provincia'), datos.get('ciudad')
        if pais and provincia and ciudad:
            try:
                UbicacionService.validar(pais, provincia, ciudad)
            except ValidationError as error:
                # El service dice en qué campo está el problema (provincia o ciudad): el error sale debajo de él
                for campo, mensajes in error.message_dict.items():
                    self.add_error(campo, mensajes)
        return datos


class VerificarCodigoForm(forms.Form):
    codigo = forms.CharField(label='Código', max_length=6, min_length=6, validators=[RegexValidator(r'^\d{6}$', 'Escribe los 6 números del código.')])
