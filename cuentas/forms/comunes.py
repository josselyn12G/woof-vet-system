"""Etiquetas y estilo que comparten los formularios de cuentas (y los del panel de otras apps)."""
from django import forms


ETIQUETAS = {
    'username': 'Usuario',
    'first_name': 'Nombre',
    'last_name': 'Apellido',
    'email': 'Correo',
    'telefono': 'Teléfono',
    'cedula': 'Cédula',
    'sector': 'Sector',
    'rol': 'Rol',
    'is_active': 'Cuenta activa',
}
# Solo cambian cómo se ve el campo: teclado numérico en el celular y como máximo 10 caracteres
CEDULA = forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 10, 'placeholder': '10 números'})


def con_estilo_del_panel(formulario):
    """Clases del panel en cada campo (las casillas quedan como están)."""
    for campo in formulario.fields.values():
        if not isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs['class'] = 'control-panel'
