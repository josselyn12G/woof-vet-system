import re
import time

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Roles, Usuario
from .validators import CEDULA_NO_VALIDA, validar_cedula
from .views import variacion


def crear_usuario(**datos):
    """Crea un usuario válido; cada prueba cambia solo el dato que le interesa."""
    valores = {
        'username': 'ana',
        'email': 'ana@woof.ec',
        'telefono': '+593987654321',
        'password': 'Clave-segura-123',
        'cedula': '1710034065',
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
            crear_usuario(username='luis', cedula='0926687856')

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
        sin_nombre = crear_usuario(username='luis', email='luis@woof.ec', cedula='0926687856')
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
            'email': 'luis@woof.ec', 'telefono': '+593987654322', 'cedula': '0926687856',
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


class CedulaTests(TestCase):
    """La cédula es el dato sensible: se valida en el servidor (validar_cedula) y en la base (unique y CheckConstraint)."""

    def test_cedula_valida_pasa(self):
        for cedula in ('1710034065', '0926687856'):
            validar_cedula(cedula)  # no lanza error

    def test_cedulas_invalidas_se_rechazan(self):
        casos = {
            '1710034064': 'dígito verificador incorrecto',
            '2510034065': 'provincia 25',
            '1790034065': 'tercer dígito 9',
            '17100340A5': 'tiene una letra',
            '171003406': 'solo 9 dígitos',
        }
        for cedula, motivo in casos.items():
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError):
                validar_cedula(cedula)

    def test_registro_rechaza_cedula_invalida_sin_importar_el_js(self):
        # El POST llega directo al servidor, como si el JavaScript estuviera desactivado
        datos = {
            'username': 'luis', 'first_name': 'Luis', 'last_name': 'Pérez',
            'email': 'luis@woof.ec', 'telefono': '+593987654322', 'cedula': '1710034064',
            'password1': 'Clave-segura-123', 'password2': 'Clave-segura-123',
        }
        respuesta = self.client.post(reverse('cuentas:registro'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, CEDULA_NO_VALIDA)
        self.assertFalse(Usuario.objects.filter(username='luis').exists())

    def test_la_cedula_no_se_repite(self):
        crear_usuario()
        with self.assertRaises(IntegrityError):
            crear_usuario(username='luis', email='luis@woof.ec')  # misma cédula 1710034065

    def test_la_base_rechaza_una_cedula_sin_formato(self):
        crear_usuario()
        # update() va directo a SQL sin pasar por validar_cedula: solo la CheckConstraint lo detiene
        with self.assertRaises(IntegrityError):
            Usuario.objects.filter(username='ana').update(cedula='abc')


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
        # Sin ?next= va al panel, que a su vez lleva a la portada del rol (aquí, cliente)
        self.assertRedirects(respuesta, reverse('cuentas:panel'), target_status_code=302)
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

    def test_codigo_vencido_vuelve_al_login(self):
        codigo = self.pasar_contrasena()
        # Se adelanta el vencimiento al pasado, en vez de esperar 5 minutos
        sesion = self.client.session
        sesion['codigo_2fa_vence'] = time.time() - 1
        sesion.save()
        respuesta = self.client.post(reverse('cuentas:verificar'), {'codigo': codigo})
        self.assertRedirects(respuesta, reverse('cuentas:login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('pre_2fa_user', self.client.session)

    def test_cancelar_cierra_la_ventana_del_codigo(self):
        # Pasa la contraseña, pulsa "Cancelar" (vuelve al login) y luego intenta abrir /verificar/
        self.pasar_contrasena()
        self.client.get(reverse('cuentas:login'))
        self.assertNotIn('pre_2fa_user', self.client.session)
        respuesta = self.client.get(reverse('cuentas:verificar'))
        self.assertRedirects(respuesta, reverse('cuentas:login'))

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


# ---------------------------------------------------------------------------
# Roles y panel: cada rol entra solo a lo suyo
# ---------------------------------------------------------------------------
def cedula_valida(numero):
    """Cédula válida de Pichincha (módulo 10) a partir de un número: distinta para cada usuario de prueba."""
    base = f'171{numero:06d}'
    suma = 0
    for digito, coeficiente in zip(base, [2, 1, 2, 1, 2, 1, 2, 1, 2]):
        producto = int(digito) * coeficiente
        suma += producto - 9 if producto > 9 else producto
    return base + str((10 - suma % 10) % 10)


def usuario_con_rol(username, rol, numero):
    return crear_usuario(username=username, email=f'{username}@woof.ec', cedula=cedula_valida(numero), rol=rol)


class AccesoPorRolTests(TestCase):
    """RolRequeridoMixin: sin sesión manda al login; con sesión pero otro rol responde 403."""

    def setUp(self):
        self.cliente = usuario_con_rol('ana', Roles.CLIENTE, 1)
        self.veterinario = usuario_con_rol('dra.paredes', Roles.VETERINARIO, 2)
        self.administrador = usuario_con_rol('jefa', Roles.ADMINISTRADOR, 3)
        # Qué pantallas del panel puede abrir cada rol
        self.pantallas = {
            'cuentas:inicio_cliente': {Roles.CLIENTE},
            'cuentas:inicio_veterinario': {Roles.VETERINARIO},
            'cuentas:inicio_administrador': {Roles.ADMINISTRADOR},
            'cuentas:usuarios': {Roles.ADMINISTRADOR},
            'cuentas:reporte_usuarios': {Roles.ADMINISTRADOR},
        }

    def test_sin_sesion_redirige_al_login(self):
        for nombre in [*self.pantallas, 'cuentas:panel']:
            with self.subTest(pantalla=nombre):
                url = reverse(nombre)
                respuesta = self.client.get(url)
                self.assertRedirects(respuesta, f"{reverse('cuentas:login')}?next={url}")

    def test_cada_rol_entra_solo_a_sus_pantallas(self):
        for usuario in (self.cliente, self.veterinario, self.administrador):
            self.client.force_login(usuario)
            for nombre, roles in self.pantallas.items():
                with self.subTest(rol=usuario.rol, pantalla=nombre):
                    respuesta = self.client.get(reverse(nombre))
                    self.assertEqual(respuesta.status_code, 200 if usuario.rol in roles else 403)

    def test_el_cliente_no_puede_editar_usuarios(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.cliente.pk]),
            {'rol': Roles.ADMINISTRADOR, 'is_active': 'on'},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rol, Roles.CLIENTE)  # no pudo darse el rol de administrador


class PanelTests(TestCase):
    """/panel/ no dibuja nada: manda a cada usuario a la portada de su rol."""

    def test_redirige_a_la_portada_de_cada_rol(self):
        destinos = [
            (Roles.CLIENTE, 'cuentas:inicio_cliente'),
            (Roles.VETERINARIO, 'cuentas:inicio_veterinario'),
            (Roles.ADMINISTRADOR, 'cuentas:inicio_administrador'),
        ]
        for numero, (rol, destino) in enumerate(destinos, start=1):
            with self.subTest(rol=rol):
                self.client.force_login(usuario_con_rol(f'persona{numero}', rol, numero))
                respuesta = self.client.get(reverse('cuentas:panel'))
                self.assertRedirects(respuesta, reverse(destino))

    def test_periodo_inventado_vuelve_al_de_siempre(self):
        # ?periodo= viene de la URL: un valor que no existe no rompe la página, usa el período por defecto
        self.client.force_login(usuario_con_rol('jefa', Roles.ADMINISTRADOR, 1))
        respuesta = self.client.get(reverse('cuentas:inicio_administrador'), {'periodo': 'nada'})
        self.assertEqual(respuesta.context['periodo'], 'mes')

        self.client.force_login(usuario_con_rol('dra.paredes', Roles.VETERINARIO, 2))
        respuesta = self.client.get(reverse('cuentas:inicio_veterinario'), {'periodo': 'nada'})
        self.assertEqual(respuesta.context['periodo'], '7d')

    def test_variacion_no_inventa_porcentajes(self):
        # Sin datos del período anterior no hay porcentaje que calcular
        self.assertEqual(variacion(0, 0), {'texto': '—', 'tipo': 'neutro'})
        self.assertEqual(variacion(3, 0), {'texto': '+3 nuevas', 'tipo': 'nuevo'})
        self.assertEqual(variacion(15, 10), {'texto': '50,0%', 'tipo': 'sube'})
        self.assertEqual(variacion(5, 10), {'texto': '50,0%', 'tipo': 'baja'})


class GestionUsuariosTests(TestCase):
    """Usuarios del panel del administrador: buscar, filtrar, cambiar el rol y el reporte CSV."""

    def setUp(self):
        self.administrador = usuario_con_rol('jefa', Roles.ADMINISTRADOR, 1)
        self.cliente = usuario_con_rol('ana', Roles.CLIENTE, 2)
        self.otro = usuario_con_rol('luis', Roles.CLIENTE, 3)
        self.client.force_login(self.administrador)

    def test_busca_por_cedula(self):
        respuesta = self.client.get(reverse('cuentas:usuarios'), {'q': self.cliente.cedula})
        self.assertEqual(list(respuesta.context['usuarios']), [self.cliente])

    def test_filtra_por_rol_e_ignora_un_rol_inventado(self):
        respuesta = self.client.get(reverse('cuentas:usuarios'), {'rol': Roles.ADMINISTRADOR})
        self.assertEqual(list(respuesta.context['usuarios']), [self.administrador])
        respuesta = self.client.get(reverse('cuentas:usuarios'), {'rol': 'superheroe'})
        self.assertEqual(len(respuesta.context['usuarios']), 3)

    def test_da_el_rol_de_veterinario(self):
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.cliente.pk]),
            {'rol': Roles.VETERINARIO, 'is_active': 'on'},
        )
        self.assertRedirects(respuesta, reverse('cuentas:usuarios'))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rol, Roles.VETERINARIO)

    def test_rol_inventado_no_se_guarda(self):
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.cliente.pk]),
            {'rol': 'superheroe', 'is_active': 'on'},
        )
        self.assertEqual(respuesta.status_code, 200)  # vuelve a mostrar el formulario con el error
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rol, Roles.CLIENTE)

    def test_el_administrador_no_se_quita_su_propio_rol(self):
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.administrador.pk]),
            {'rol': Roles.CLIENTE, 'is_active': 'on'},
        )
        self.assertContains(respuesta, 'No puedes quitarte el rol de administrador')
        self.administrador.refresh_from_db()
        self.assertEqual(self.administrador.rol, Roles.ADMINISTRADOR)

    def test_el_administrador_no_se_desactiva(self):
        # Sin 'is_active' en el POST, la casilla llega desmarcada
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.administrador.pk]),
            {'rol': Roles.ADMINISTRADOR},
        )
        self.assertContains(respuesta, 'ni desactivar tu propia cuenta')
        self.administrador.refresh_from_db()
        self.assertTrue(self.administrador.is_active)

    def test_reporte_csv_sin_contrasenas(self):
        respuesta = self.client.get(reverse('cuentas:reporte_usuarios'))
        self.assertEqual(respuesta['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', respuesta['Content-Disposition'])
        contenido = respuesta.content.decode('utf-8-sig')
        self.assertTrue(contenido.startswith('Usuario,Nombre,Correo,Rol,Cédula'))
        self.assertIn(self.cliente.cedula, contenido)
        self.assertNotIn(self.cliente.password, contenido)  # el hash de la contraseña nunca sale
