from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Roles, Usuario


def crear_usuario(**datos):
    """Crea un usuario válido; cada prueba cambia solo el dato que le interesa."""
    valores = {
        'username': 'ana',
        'email': 'ana@woof.ec',
        'telefono': '+593987654321',
        'password': 'Clave-segura-123',
    }
    valores.update(datos)
    # create_user (y no Usuario(...).save()) para que la contraseña se guarde cifrada.
    return Usuario.objects.create_user(**valores)


class UsuarioModelTests(TestCase):
    def test_rol_por_defecto_es_cliente(self):
        usuario = crear_usuario()
        self.assertEqual(usuario.rol, Roles.CLIENTE)

    def test_contrasena_se_guarda_cifrada(self):
        usuario = crear_usuario()
        # En la base no queda el texto original, sino un hash...
        self.assertNotEqual(usuario.password, 'Clave-segura-123')
        # ...pero Django sí puede comprobar si una contraseña coincide con ese hash.
        self.assertTrue(usuario.check_password('Clave-segura-123'))

    def test_correo_es_unico(self):
        crear_usuario()
        # Otro username, mismo correo: la base de datos lo rechaza por unique=True.
        with self.assertRaises(IntegrityError):
            crear_usuario(username='luis')

    def test_telefono_debe_ser_internacional(self):
        usuario = crear_usuario()
        usuario.telefono = '0987654321'
        # full_clean() ejecuta los validadores de Django; save() no los ejecutaría.
        with self.assertRaises(ValidationError) as error:
            usuario.full_clean()
        self.assertIn('telefono', error.exception.message_dict)

    def test_la_base_rechaza_un_rol_invalido(self):
        crear_usuario()
        # update() va directo a SQL sin pasar por Django: solo la CheckConstraint lo detiene.
        with self.assertRaises(IntegrityError):
            Usuario.objects.filter(username='ana').update(rol='superjefe')

    def test_str_muestra_nombre_o_usuario(self):
        con_nombre = crear_usuario(first_name='Ana', last_name='Pérez')
        sin_nombre = crear_usuario(username='luis', email='luis@woof.ec')
        self.assertEqual(str(con_nombre), 'Ana Pérez')
        self.assertEqual(str(sin_nombre), 'luis')


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()

    def test_la_pagina_de_login_carga(self):
        respuesta = self.client.get(reverse('cuentas:login'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'cuentas/login.html')

    def test_login_correcto_inicia_sesion(self):
        respuesta = self.client.post(reverse('cuentas:login'), {'username': 'ana', 'password': 'Clave-segura-123'})
        self.assertRedirects(respuesta, reverse('cuentas:inicio'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_incorrecto_muestra_error(self):
        respuesta = self.client.post(reverse('cuentas:login'), {'username': 'ana', 'password': '123'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Usuario o contraseña incorrectos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_cierra_la_sesion(self):
        self.client.login(username='ana', password='Clave-segura-123')
        respuesta = self.client.post(reverse('cuentas:logout'))
        self.assertRedirects(respuesta, reverse('cuentas:inicio'))
        self.assertNotIn('_auth_user_id', self.client.session)


class RegistroTests(TestCase):
    def setUp(self):
        self.datos = {
            'username': 'luis', 'first_name': 'Luis', 'last_name': 'Pérez',
            'email': 'luis@woof.ec', 'telefono': '+593987654322',
            'password1': 'Clave-segura-123', 'password2': 'Clave-segura-123',
        }

    def test_registro_crea_usuario_cliente(self):
        respuesta = self.client.post(reverse('cuentas:registro'), self.datos)
        self.assertRedirects(respuesta, reverse('cuentas:login'))
        self.assertTrue(Usuario.objects.filter(username='luis').exists())
        usuario = Usuario.objects.get(username='luis')
        self.assertEqual(usuario.rol, Roles.CLIENTE)

    def test_registro_ignora_el_rol_enviado(self):
        # Alguien modifica el formulario en el navegador para registrarse como administrador
        self.datos['rol'] = 'administrador'
        self.client.post(reverse('cuentas:registro'), self.datos)
        # "rol" no está en los fields de RegistroForm: Django lo ignora y queda como cliente
        usuario = Usuario.objects.get(username='luis')
        self.assertEqual(usuario.rol, Roles.CLIENTE)
