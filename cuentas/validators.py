from django.core.exceptions import ValidationError

# Un solo mensaje para las reglas internas (provincia, tercer dígito, verificador):
CEDULA_NO_VALIDA = "Ingresa un número de cédula válido."

def validar_cedula(cedula):
    """Valida una cédula ecuatoriana: formato, provincia, tercer dígito y dígito verificador (módulo 10)."""
    validar_cantidad_digitos(cedula)
    validar_numero_provincia(cedula)
    validar_tercer_digito(cedula)
    validar_digito_verificador(cedula)


def validar_cantidad_digitos(cedula):
    if len(cedula) != 10 or not cedula.isdigit():
        raise ValidationError('La cédula debe tener 10 números, sin letras ni espacios.')


def validar_numero_provincia(cedula):
    provincia = int(cedula[:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        raise ValidationError(CEDULA_NO_VALIDA)


def validar_tercer_digito(cedula):
    tercer_digito = int(cedula[2])
    if tercer_digito >= 6:
        raise ValidationError(CEDULA_NO_VALIDA)


def validar_digito_verificador(cedula):
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for digito, coeficiente in zip(cedula[:9], coeficientes):
        producto = int(digito) * coeficiente
        if producto > 9:
            producto -= 9
        suma += producto
    verificador = (10 - suma % 10) % 10
    if verificador != int(cedula[-1]):
        raise ValidationError(CEDULA_NO_VALIDA)
