"""Mi cuenta: editar mis datos (HU-22) y cambiar mi contraseña (HU-21)."""
from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from ..models import Usuario
from ..services.ubicacion import UbicacionService
from .comunes import ETIQUETAS, con_estilo_del_panel
from .ubicacion import UbicacionMixin


class MiCuentaForm(UbicacionMixin, forms.ModelForm):
    """
    Nombre, correo, teléfono y ciudad. La cédula, el usuario y el rol no se cambian aquí.
    Si cambia el correo, vuelve a quedar sin verificar (la vista manda el enlace al correo nuevo).
    """

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'ciudad']
        labels = {campo: ETIQUETAS[campo] for campo in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ciudad = self.instance.ciudad
        if ciudad:
            self.preparar_ubicacion(pais=ciudad.provincia.pais_id, provincia=ciudad.provincia_id)
        else:
            self.preparar_ubicacion(pais=getattr(UbicacionService.pais_por_defecto(), 'pk', None))
        con_estilo_del_panel(self)

    def clean(self):
        datos = super().clean()
        self.validar_ubicacion(datos)
        return datos

    def cambio_el_correo(self):
        return 'email' in self.changed_data


class CambiarContrasenaForm(PasswordChangeForm):
    """La de Django (contraseña actual y la nueva dos veces, con las mismas reglas del registro), con el estilo del panel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        con_estilo_del_panel(self)
