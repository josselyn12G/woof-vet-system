"""La ficha de una mascota que llena el cliente («Mis mascotas»)."""
from datetime import date

from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from ..models import Mascota
from ..services import CatalogoService, MascotaService, preparar_foto
from .comunes import (
    CAMPOS_OBLIGATORIOS, EDAD_MAXIMA_ANIOS, FORMATOS_FOTO, MENSAJES_OBLIGATORIOS, PESO_MAXIMO_KG, SOLO_LETRAS,
    TAMANO_MAXIMO_FOTO_MB,
)


class MascotaForm(forms.ModelForm):
    # La foto no es un campo del modelo que se copie tal cual: se valida aquí y save() la convierte a WEBP
    foto = forms.ImageField(
        label='Foto',
        required=False,
        help_text=f'Opcional. JPG, PNG o WEBP de hasta {TAMANO_MAXIMO_FOTO_MB} MB.',
        validators=[FileExtensionValidator(FORMATOS_FOTO, 'Sube una foto en formato JPG, PNG o WEBP.')],
        # accept: el selector de archivos del navegador solo muestra imágenes de estos formatos
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )
    quitar_foto = forms.BooleanField(label='Quitar la foto actual', required=False)

    class Meta:
        model = Mascota
        # Sin "dueno": lo asigna la vista con request.user
        fields = ['nombre', 'especie', 'raza', 'sexo', 'fecha_nacimiento', 'peso_kg']
        labels = {
            'nombre': 'Nombre',
            'especie': 'Especie',
            'raza': 'Raza',
            'sexo': 'Sexo',
            'fecha_nacimiento': 'Fecha de nacimiento',
            'peso_kg': 'Peso (kg)',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej.: Firulais', 'autofocus': True}),
            # razas.js deja en "Raza" solo las de la especie elegida
            'especie': forms.Select(attrs={'data-elige-especie': ''}),
            'raza': forms.Select(attrs={'data-elige-raza': ''}),
            'fecha_nacimiento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'peso_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'max': '150', 'placeholder': 'Ej.: 12.5'}),
        }

    def __init__(self, *args, dueno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dueno = dueno  # para no repetir el nombre entre las mascotas del mismo cliente
        for nombre in CAMPOS_OBLIGATORIOS:
            campo = self.fields[nombre]
            campo.required = True
            campo.error_messages['required'] = MENSAJES_OBLIGATORIOS[nombre]
        # Sin la opción vacía "---------" en el sexo ahora que es obligatorio
        self.fields['sexo'].choices = [('', 'Elige una opción')] + list(self.fields['sexo'].choices)[1:]
        self.preparar_especie_y_raza()
        # El calendario del navegador no deja elegir fechas futuras (el modelo lo valida igual)
        self.fields['fecha_nacimiento'].widget.attrs['max'] = timezone.localdate().isoformat()
        # Clases de Bootstrap: las listas usan form-select, las casillas form-check-input y el resto form-control
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.Select):
                clase = 'form-select'
            elif isinstance(campo.widget, forms.CheckboxInput):
                clase = 'form-check-input'
            else:
                clase = 'form-control'
            campo.widget.attrs['class'] = clase

    def preparar_especie_y_raza(self):
        """
        Especies y razas activas del catálogo (al editar, también la que ya tiene aunque se haya desactivado).
        Las razas van agrupadas por especie: sin JavaScript se elige igual; razas.js muestra solo un grupo.
        Que la raza sea de la especie elegida lo valida Mascota.clean().
        """
        especie, raza = self.fields['especie'], self.fields['raza']
        especie.queryset = CatalogoService.especies_para_elegir(self.instance.especie_id)
        especie.empty_label = 'Elige una opción'
        raza.queryset = CatalogoService.razas_para_elegir(especie.queryset, self.instance.raza_id)
        grupos = {}
        for opcion in raza.queryset:
            grupos.setdefault(opcion.especie.nombre, []).append((opcion.pk, opcion.nombre))
        raza.choices = [('', 'Elige la raza')] + list(grupos.items())
        raza.help_text = 'Opcional. Si no la sabes, elige "Mestizo".'

    def clean_nombre(self):
        nombre = ' '.join(self.cleaned_data['nombre'].split())  # sin espacios de más
        if len(nombre) < 2:
            raise forms.ValidationError('El nombre debe tener al menos 2 letras.')
        if not SOLO_LETRAS.match(nombre):
            raise forms.ValidationError('El nombre solo puede tener letras y espacios.')
        if self.dueno is not None and MascotaService.nombre_repetido(self.dueno, nombre, self.instance.pk):
            raise forms.ValidationError(f'Ya tienes una mascota llamada {nombre}.')
        return nombre

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data['fecha_nacimiento']
        if fecha < date(timezone.localdate().year - EDAD_MAXIMA_ANIOS, 1, 1):
            raise forms.ValidationError(f'La mascota no puede tener más de {EDAD_MAXIMA_ANIOS} años. Revisa la fecha.')
        return fecha

    def clean_peso_kg(self):
        peso = self.cleaned_data['peso_kg']
        if peso is not None and peso > PESO_MAXIMO_KG:
            raise forms.ValidationError(f'El peso no puede ser mayor que {PESO_MAXIMO_KG} kg. Revisa el valor.')
        return peso

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto and foto.size > TAMANO_MAXIMO_FOTO_MB * 1024 * 1024:
            raise forms.ValidationError(f'La foto no puede pesar más de {TAMANO_MAXIMO_FOTO_MB} MB.')
        return foto

    def save(self, commit=True):
        mascota = super().save(commit=False)
        # Foto nueva: se guarda reducida. Sin foto nueva y con la casilla marcada: se borra.
        # Sin ninguna de las dos: se conserva la que había.
        if self.cleaned_data.get('foto'):
            mascota.foto = preparar_foto(self.cleaned_data['foto'])
        elif self.cleaned_data.get('quitar_foto'):
            mascota.foto = None
        if commit:
            mascota.save()
        return mascota

    def full_clean(self):
        super().full_clean()
        # Los campos con errores se pintan en rojo (is-invalid de Bootstrap)
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs['class'] += ' is-invalid'
