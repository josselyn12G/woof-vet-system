import re
import time

from django.core import mail
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

    def test_login_correcto_pide_el_codigo(self):
        respuesta = self.client.post(reverse('cuentas:login'), {'username': 'ana', 'password': 'Clave-segura-123'})
        # Con doble factor, la contraseña correcta ya no inicia sesión: manda el código y pasa a /verificar/
        self.assertRedirects(respuesta, reverse('cuentas:verificar'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session['pre_2fa_user'], self.usuario.pk)
        # En las pruebas no se envían correos reales: quedan guardados en mail.outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@woof.ec'])

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


class DobleFactorTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()

    def pasar_contrasena(self, siguiente=None):
        """Primer paso del login. Devuelve el código, leído del correo como lo haría la persona."""
        datos = {'username': 'ana', 'password': 'Clave-segura-123'}
        if siguiente:
            datos['next'] = siguiente
        self.client.post(reverse('cuentas:login'), datos)
        return re.search(r'\d{6}', mail.outbox[-1].body).group()

    def test_verificar_sin_contrasena_redirige_al_login(self):
        # Entrar directo a /verificar/ sin haber pasado la contraseña
        respuesta = self.client.get(reverse('cuentas:verificar'))
        self.assertRedirects(respuesta, reverse('cuentas:login'))

    def test_la_pagina_de_verificar_carga(self):
        self.pasar_contrasena()
        respuesta = self.client.get(reverse('cuentas:verificar'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'cuentas/verificar.html')

    def test_codigo_correcto_inicia_sesion(self):
        codigo = self.pasar_contrasena()
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': codigo})
        self.assertRedirects(respuesta, reverse('cuentas:inicio'))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.usuario.pk))
        # Los datos del "login a medias" y el código se borran: no se pueden volver a usar
        for clave in ('pre_2fa_user', 'pre_2fa_next', 'codigo_2fa', 'codigo_2fa_vence'):
            self.assertNotIn(clave, self.client.session)

    def test_codigo_incorrecto_no_inicia_sesion(self):
        codigo = self.pasar_contrasena()
        incorrecto = '000000' if codigo != '000000' else '111111'
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': incorrecto})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El código es incorrecto o ya venció.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_codigo_vencido_no_inicia_sesion(self):
        codigo = self.pasar_contrasena()
        # Se adelanta el vencimiento al pasado, en vez de esperar 5 minutos
        sesion = self.client.session
        sesion['codigo_2fa_vence'] = time.time() - 1
        sesion.save()
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': codigo})
        self.assertContains(respuesta, 'El código es incorrecto o ya venció.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_codigo_con_letras_muestra_error(self):
        self.pasar_contrasena()
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': 'abc123'})
        self.assertContains(respuesta, 'Escribe los 6 números del código.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_vuelve_a_la_pagina_que_pedia(self):
        # Si venía de una página protegida (?next=), al terminar vuelve ahí
        codigo = self.pasar_contrasena(siguiente=reverse('cuentas:registro'))
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': codigo})
        self.assertRedirects(respuesta, reverse('cuentas:registro'))
