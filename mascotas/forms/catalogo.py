"""Las especies y razas del catálogo (superadministrador)."""
from django import forms
from django.utils.text import slugify

from cuentas.forms import con_estilo_del_panel

from ..models import Especie, Raza
from ..services import CatalogoService
from .comunes import sin_espacios_de_mas


class EspecieForm(forms.ModelForm):
    """Una especie del catálogo. El código (para las URLs y el CSS) se arma solo con el nombre al crearla."""

    class Meta:
        model = Especie
        fields = ['nombre', 'plural', 'orden', 'activa']
        labels = {'nombre': 'Nombre', 'plural': 'Nombre en plural', 'orden': 'Orden', 'activa': 'Especie activa'}
        help_texts = {
            'plural': 'Se usa en los filtros y las cifras: "Conejos", "Peces".',
            'activa': 'Si la desactivas ya no se ofrece al registrar una mascota; las que la tienen la conservan.',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej.: Conejo'}),
            'plural': forms.TextInput(attrs={'placeholder': 'Ej.: Conejos'}),
            'orden': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_estilo_del_panel(self)

    def clean_nombre(self):
        nombre = sin_espacios_de_mas(self.cleaned_data['nombre'])
        if CatalogoService.especie_repetida(nombre, self.instance.pk):
            raise forms.ValidationError('Ya existe una especie con ese nombre.')
        if not self.instance.pk:
            codigo = slugify(nombre)
            if not codigo:
                raise forms.ValidationError('El nombre debe tener letras.')
            if CatalogoService.codigo_usado(codigo):
                raise forms.ValidationError('Ya existe una especie con un nombre casi igual.')
            self.instance.codigo = codigo
        return nombre

    def clean_plural(self):
        return sin_espacios_de_mas(self.cleaned_data['plural'])


class EspecieOpcion(forms.ModelChoiceField):
    def label_from_instance(self, especie):
        return especie.nombre if especie.activa else f'{especie.nombre} (desactivada)'


class RazaForm(forms.ModelForm):
    """Una raza del catálogo. No se repite el nombre dentro de la misma especie."""
    especie = EspecieOpcion(label='Especie', queryset=CatalogoService.especies(), empty_label='Elige la especie')

    class Meta:
        model = Raza
        fields = ['especie', 'nombre', 'activa']
        labels = {'nombre': 'Nombre', 'activa': 'Raza activa'}
        help_texts = {'activa': 'Si la desactivas ya no se ofrece al registrar; las mascotas que la tienen la conservan.'}
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej.: Shar Pei'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_estilo_del_panel(self)

    def clean_nombre(self):
        return sin_espacios_de_mas(self.cleaned_data['nombre'])

    def clean(self):
        datos = super().clean()
        especie, nombre = datos.get('especie'), datos.get('nombre')
        if especie and nombre and CatalogoService.raza_repetida(especie, nombre, self.instance.pk):
            self.add_error('nombre', f'{especie} ya tiene la raza {nombre}.')
        return datos
