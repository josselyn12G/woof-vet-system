import re
from datetime import date
from decimal import Decimal

from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.utils.text import slugify

from cuentas.forms import con_estilo_del_panel

from .models import Especie, Mascota, Raza
from .services import CatalogoService, MascotaService, preparar_foto

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


# ---------------------------------------------------------------------------
# Catálogo de especies y razas (superadministrador)
# ---------------------------------------------------------------------------
def sin_espacios_de_mas(texto):
    return ' '.join(texto.split())


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
