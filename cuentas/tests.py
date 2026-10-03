from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

Usuario = get_user_model()


def crear_usuario(**datos):
    valores = {'username': 'ana', 'email': 'ana@woof.ec', 'telefono': '+593987654321', 'password': 'Clave-segura-123'}
    valores.update(datos)
    return Usuario.objects.create_user(**valores)


class UsuarioModelTests(TestCase):
    def test_django_usa_el_modelo_propio(self):
        self.assertEqual(Usuario._meta.label, 'cuentas.Usuario')

    def test_rol_por_defecto_es_cliente(self):
        self.assertEqual(crear_usuario().rol, Usuario.Rol.CLIENTE)

    def test_la_contrasena_se_guarda_cifrada(self):
        usuario = crear_usuario()
        self.assertNotEqual(usuario.password, 'Clave-segura-123')
        self.assertTrue(usuario.check_password('Clave-segura-123'))

    def test_el_correo_es_unico(self):
        crear_usuario()
        with self.assertRaises(IntegrityError):
            crear_usuario(username='luis')

    def test_telefono_debe_ser_internacional(self):
        usuario = crear_usuario()
        usuario.telefono = '0987654321'
        with self.assertRaises(ValidationError) as error:
            usuario.full_clean()
        self.assertIn('telefono', error.exception.message_dict)

    def test_str_usa_el_nombre_completo(self):
        self.assertEqual(str(crear_usuario(first_name='Ana', last_name='Pérez')), 'Ana Pérez')
        self.assertEqual(str(crear_usuario(username='luis', email='luis@woof.ec')), 'luis')
