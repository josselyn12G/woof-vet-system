"""La reserva del cliente: mascota, servicio, veterinario, fecha y hora."""
from datetime import datetime

from django import forms
from django.utils import timezone

from mascotas.services import MascotaService

from ..services import CitaService, ServicioService
from .campos import VeterinarioOpcion


class AgendarCitaForm(forms.Form):
    """
    Datos para agendar una cita: mascota, servicio, veterinario, fecha y hora.

    Valida la entrada (mascota propia, fecha futura, veterinario del servicio);
    que el turno siga libre lo decide AgendaService al guardar.
    """
    mascota = forms.ModelChoiceField(label='Mascota', queryset=MascotaService.fichas().none(), empty_label='Elige a tu mascota')
    # Solo servicios activos que alguien atiende: los demás no se pueden agendar
    servicio = forms.ModelChoiceField(
        label='Servicio',
        queryset=ServicioService.agendables(),
        empty_label='Elige un servicio',
    )
    veterinario = VeterinarioOpcion(
        label='Veterinario',
        queryset=CitaService.veterinarios(activos=True),
        empty_label='Elige primero el servicio',
    )
    fecha = forms.DateField(label='Fecha', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    # La hora llega como "09:30" desde los botones de horas libres
    hora = forms.TimeField(label='Hora', input_formats=['%H:%M'])
    motivo = forms.CharField(label='Motivo', max_length=200, required=False)

    def __init__(self, *args, cliente, **kwargs):
        super().__init__(*args, **kwargs)
        # Desplegable con FK filtrada: el cliente solo ve (y solo puede enviar) sus mascotas
        # tiene_foto basta para mostrar su foto en la tarjeta, sin traer los bytes
        self.fields['mascota'].queryset = MascotaService.del_dueno(cliente)

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('Ese día ya pasó: elige hoy o una fecha futura.')
        return fecha

    def clean(self):
        datos = super().clean()
        servicio = datos.get('servicio')
        veterinario = datos.get('veterinario')
        # Desplegable dependiente: el veterinario debe atender el servicio elegido
        if servicio and veterinario and not ServicioService.lo_atiende(servicio, veterinario):
            self.add_error('veterinario', 'Ese veterinario no atiende este servicio.')
        # Fecha y hora se unen en un solo momento con la zona horaria de Ecuador
        if datos.get('fecha') and datos.get('hora'):
            datos['inicio'] = timezone.make_aware(datetime.combine(datos['fecha'], datos['hora']))
        return datos


class ReprogramarCitaForm(forms.Form):
    """
    La nueva fecha y hora de una cita. Solo valida la entrada; si el turno sigue libre
    lo decide AgendaService.reprogramar() dentro de su transacción.
    """
    fecha = forms.DateField(label='Nueva fecha', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    hora = forms.TimeField(label='Nueva hora', input_formats=['%H:%M'])

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('Ese día ya pasó: elige hoy o una fecha futura.')
        return fecha

    def clean(self):
        datos = super().clean()
        if datos.get('fecha') and datos.get('hora'):
            datos['inicio'] = timezone.make_aware(datetime.combine(datos['fecha'], datos['hora']))
        return datos
