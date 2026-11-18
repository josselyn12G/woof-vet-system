"""Los filtros de la gestión de citas, de los indicadores de la agenda y de las reseñas."""
from datetime import timedelta

from django import forms
from django.utils import timezone

from ..models import ESTRELLAS_MAX, ESTRELLAS_MIN, EstadoCita
from ..services import CitaService, ServicioService
from .campos import VeterinarioOpcion


class FiltroCitasForm(forms.Form):
    """Filtros de la gestión de citas (administrador). Todos opcionales y por GET: un valor inventado
    en la URL no rompe la página, el campo queda sin filtrar."""
    q = forms.CharField(required=False, max_length=80)
    estado = forms.ChoiceField(required=False, choices=[('', 'Todos los estados')] + EstadoCita.choices)
    veterinario = VeterinarioOpcion(required=False, queryset=CitaService.veterinarios().none(),
                                    empty_label='Todos los veterinarios')
    servicio = forms.ModelChoiceField(required=False, queryset=ServicioService.todos(), empty_label='Todos los servicios')

    def __init__(self, *args, veterinarios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veterinario'].queryset = veterinarios
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'control-panel'
            if isinstance(campo.widget, forms.Select):
                # Como en los demás filtros del panel: elegir una opción ya filtra
                campo.widget.attrs.update({'class': 'control-panel filtros__rol', 'onchange': 'this.form.submit()'})

    def filtros(self):
        """Los filtros válidos; los que no pasan la validación se ignoran."""
        self.is_valid()
        datos = getattr(self, 'cleaned_data', {})
        return {
            'buscar': (datos.get('q') or '').strip(),
            'estado': datos.get('estado') or '',
            'veterinario': datos.get('veterinario'),
            'servicio': datos.get('servicio'),
        }


# El reporte abre con los últimos 30 días y no acepta rangos de más de un año (sería muy lento)
DIAS_POR_DEFECTO = 30
DIAS_MAXIMOS = 366


class IndicadoresForm(forms.Form):
    """
    El rango de fechas y el veterinario de los indicadores (RF-25). Va por GET: sin datos, o con datos
    que no pasan la validación, rango() devuelve los últimos 30 días para que la página siempre muestre algo.
    """
    desde = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'control-panel'}, format='%Y-%m-%d'))
    hasta = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'control-panel'}, format='%Y-%m-%d'))
    veterinario = VeterinarioOpcion(required=False, queryset=CitaService.veterinarios().none(),
                                    empty_label='Todos los veterinarios',
                                    widget=forms.Select(attrs={'class': 'control-panel'}))

    def __init__(self, *args, veterinarios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veterinario'].queryset = veterinarios

    @staticmethod
    def rango_por_defecto():
        hoy = timezone.localdate()
        return hoy - timedelta(days=DIAS_POR_DEFECTO - 1), hoy

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('desde'), datos.get('hasta')
        if desde and hasta:
            if desde > hasta:
                raise forms.ValidationError('La fecha "desde" debe ser anterior o igual a "hasta".')
            if (hasta - desde).days >= DIAS_MAXIMOS:
                raise forms.ValidationError('Elige un rango de un año como máximo.')
        return datos

    def filtros(self):
        """(desde, hasta, veterinario) válidos; si el formulario no es válido, los últimos 30 días de todos."""
        if self.is_bound and self.is_valid():
            return self.cleaned_data['desde'], self.cleaned_data['hasta'], self.cleaned_data['veterinario']
        return (*self.rango_por_defecto(), None)


class FiltroCalificacionesForm(forms.Form):
    """
    Filtros de las reseñas (por GET y opcionales, como los de la gestión de citas). Sin veterinarios
    (Mis calificaciones del veterinario) el campo veterinario no existe y solo se filtra por estrellas.
    """
    veterinario = VeterinarioOpcion(required=False, queryset=CitaService.veterinarios().none(),
                                    empty_label='Todos los veterinarios')
    estrellas = forms.TypedChoiceField(
        required=False, coerce=int, empty_value=None,
        choices=[('', 'Todas las estrellas')] + [
            (n, f'{n} estrella{"s" if n > 1 else ""}') for n in range(ESTRELLAS_MAX, ESTRELLAS_MIN - 1, -1)
        ],
    )

    def __init__(self, *args, veterinarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinarios is None:
            del self.fields['veterinario']
        else:
            self.fields['veterinario'].queryset = veterinarios
        for campo in self.fields.values():
            # Elegir una opción ya filtra
            campo.widget.attrs.update({'class': 'control-panel filtros__rol', 'onchange': 'this.form.submit()'})

    def filtros(self):
        """{'veterinario', 'estrellas'} válidos; un valor inventado en la URL se ignora."""
        self.is_valid()
        datos = getattr(self, 'cleaned_data', {})
        return {'veterinario': datos.get('veterinario'), 'estrellas': datos.get('estrellas')}
