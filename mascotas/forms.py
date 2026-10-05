from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .models import Mascota
from .services import preparar_foto

TAMANO_MAXIMO_FOTO_MB = 5
FORMATOS_FOTO = ['jpg', 'jpeg', 'png', 'webp']  # los que muestran todos los navegadores


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
            'raza': forms.TextInput(attrs={'placeholder': 'Ej.: Mestizo'}),
            'fecha_nacimiento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'peso_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': 'Ej.: 12.5'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
