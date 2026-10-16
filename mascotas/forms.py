import re
from datetime import date
from decimal import Decimal

from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .models import Mascota
from .services import preparar_foto

TAMANO_MAXIMO_FOTO_MB = 5
FORMATOS_FOTO = ['jpg', 'jpeg', 'png', 'webp']  # los que muestran todos los navegadores
PESO_MAXIMO_KG = Decimal('150')
EDAD_MAXIMA_ANIOS = 35
# Letras (con tildes y ñ), espacios, guion, apóstrofo y punto: "Max", "Señor Bigotes", "Pastor Alemán"
SOLO_LETRAS = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ '.-]*$")

# Campos que el modelo deja en blanco (para el admin y los datos viejos) pero que el cliente debe llenar
CAMPOS_OBLIGATORIOS = ['nombre', 'especie', 'sexo', 'fecha_nacimiento', 'peso_kg']
MENSAJES_OBLIGATORIOS = {
    'nombre': 'Escribe el nombre de tu mascota.',
    'especie': 'Elige la especie.',
    'sexo': 'Elige si es macho o hembra.',
    'fecha_nacimiento': 'Indica la fecha de nacimiento (si no la sabes exacta, pon una aproximada).',
    'peso_kg': 'Indica el peso en kilogramos.',
}


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
        self.fields['especie'].choices = [('', 'Elige una opción')] + list(self.fields['especie'].choices)[1:]
        self.fields['raza'].help_text = 'Opcional. Si no la sabes, escribe "Mestizo".'
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

    def clean_nombre(self):
        nombre = ' '.join(self.cleaned_data['nombre'].split())  # sin espacios de más
        if len(nombre) < 2:
            raise forms.ValidationError('El nombre debe tener al menos 2 letras.')
        if not SOLO_LETRAS.match(nombre):
            raise forms.ValidationError('El nombre solo puede tener letras y espacios.')
        if self.dueno is not None:
            repetidas = Mascota.objects.filter(dueno=self.dueno, nombre__iexact=nombre).exclude(pk=self.instance.pk)
            if repetidas.exists():
                raise forms.ValidationError(f'Ya tienes una mascota llamada {nombre}.')
        return nombre

    def clean_raza(self):
        raza = ' '.join(self.cleaned_data['raza'].split())
        if raza and not SOLO_LETRAS.match(raza):
            raise forms.ValidationError('La raza solo puede tener letras y espacios.')
        return raza

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
