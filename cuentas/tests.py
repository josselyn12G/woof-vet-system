import re
import time

from django.core import mail
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import Roles, Usuario
from .validators import CEDULA_NO_VALIDA, validar_cedula
from .services import PoliticaDeCuentas, completar_login, iniciar_login_pendiente


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
        self.assertRedirects(respuesta, reverse('panel:panel'), target_status_code=302)
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
            'panel:inicio_cliente': {Roles.CLIENTE},
            'panel:inicio_veterinario': {Roles.VETERINARIO},
            'panel:inicio_administrador': {Roles.ADMINISTRADOR},
            'cuentas:usuarios': {Roles.ADMINISTRADOR},
            'cuentas:reporte_usuarios': {Roles.ADMINISTRADOR},
        }

    def test_sin_sesion_redirige_al_login(self):
        for nombre in [*self.pantallas, 'panel:panel']:
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


@override_settings(DOBLE_FACTOR=False)
class LoginSinDobleFactorTests(TestCase):
    """En Render (DJANGO_DOBLE_FACTOR=False) el login entra directo: no hay código ni correo."""

    def test_entra_directo_al_panel_sin_enviar_correo(self):
        crear_usuario()
        respuesta = self.client.post(reverse('cuentas:login'), {'username': 'ana', 'password': 'Clave-segura-123'})
        self.assertRedirects(respuesta, reverse('panel:panel'), target_status_code=302)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_contrasena_incorrecta_sigue_fallando(self):
        crear_usuario()
        self.client.post(reverse('cuentas:login'), {'username': 'ana', 'password': 'otra-clave'})
        self.assertNotIn('_auth_user_id', self.client.session)


# ---------------------------------------------------------------------------
# Superadministrador: gestiona al equipo (administradores y veterinarios)
# ---------------------------------------------------------------------------
def datos_de_personal(**cambios):
    datos = {
        'first_name': 'Mateo', 'last_name': 'Ruiz', 'username': 'mateo', 'email': 'mateo@woof.ec',
        'telefono': '+593987654321', 'cedula': cedula_valida(50), 'rol': Roles.VETERINARIO,
        'password1': 'Clave-segura-123', 'password2': 'Clave-segura-123',
    }
    datos.update(cambios)
    return datos


class SuperadminTests(TestCase):
    def setUp(self):
        self.superadmin = usuario_con_rol('sara', Roles.SUPERADMIN, 1)
        self.administrador = usuario_con_rol('jefa', Roles.ADMINISTRADOR, 2)
        self.veterinario = usuario_con_rol('dra.paredes', Roles.VETERINARIO, 3)
        self.cliente = usuario_con_rol('ana', Roles.CLIENTE, 4)
        self.client.force_login(self.superadmin)

    def test_createsuperuser_crea_un_superadministrador(self):
        persona = Usuario.objects.create_superuser('raiz', 'raiz@woof.ec', 'Clave-segura-123',
                                                   telefono='+593987654321', cedula=cedula_valida(60))
        self.assertTrue(persona.es_superadmin)
        self.assertTrue(persona.gestiona_clinica)

    def test_el_panel_lo_manda_a_su_portada(self):
        self.assertRedirects(self.client.get(reverse('panel:panel')), reverse('panel:inicio_superadmin'))

    def test_tambien_entra_a_las_pantallas_del_administrador(self):
        for nombre in ('panel:inicio_administrador', 'cuentas:usuarios', 'citas:servicios', 'citas:gestion_citas',
                       'citas:gestion_horarios', 'mascotas:gestion'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_solo_el_superadministrador_entra_al_equipo(self):
        for usuario in (self.administrador, self.veterinario, self.cliente):
            self.client.force_login(usuario)
            for nombre in ('panel:inicio_superadmin', 'cuentas:equipo', 'cuentas:equipo_crear'):
                with self.subTest(rol=usuario.rol, pantalla=nombre):
                    self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_el_equipo_no_muestra_clientes(self):
        respuesta = self.client.get(reverse('cuentas:equipo'))
        self.assertEqual(set(respuesta.context['personas']), {self.superadmin, self.administrador, self.veterinario})

    def test_crea_la_cuenta_de_un_veterinario(self):
        respuesta = self.client.post(reverse('cuentas:equipo_crear'), datos_de_personal())
        self.assertRedirects(respuesta, reverse('cuentas:equipo'))
        mateo = Usuario.objects.get(username='mateo')
        self.assertEqual(mateo.rol, Roles.VETERINARIO)
        self.assertTrue(mateo.check_password('Clave-segura-123'))

    def test_crea_la_cuenta_de_un_administrador(self):
        self.client.post(reverse('cuentas:equipo_crear'), datos_de_personal(rol=Roles.ADMINISTRADOR))
        self.assertEqual(Usuario.objects.get(username='mateo').rol, Roles.ADMINISTRADOR)

    def test_una_cuenta_nueva_del_equipo_no_es_de_cliente(self):
        respuesta = self.client.post(reverse('cuentas:equipo_crear'), datos_de_personal(rol=Roles.CLIENTE))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('rol', respuesta.context['form'].errors)
        self.assertFalse(Usuario.objects.filter(username='mateo').exists())

    def test_edita_los_datos_y_el_rol_de_un_administrador(self):
        respuesta = self.client.post(reverse('cuentas:equipo_editar', args=[self.administrador.pk]), {
            'first_name': 'Laura', 'last_name': 'Jefa', 'email': 'laura@woof.ec', 'telefono': '+593987654321',
            'cedula': self.administrador.cedula, 'sector': '', 'rol': Roles.VETERINARIO, 'is_active': 'on',
        })
        self.assertRedirects(respuesta, reverse('cuentas:equipo'))
        self.administrador.refresh_from_db()
        self.assertEqual((self.administrador.first_name, self.administrador.rol), ('Laura', Roles.VETERINARIO))

    def test_corrige_los_datos_de_un_cliente_desde_usuarios_y_vuelve_ahi(self):
        url = reverse('cuentas:equipo_editar', args=[self.cliente.pk])
        self.assertContains(self.client.get(reverse('cuentas:usuarios')), url)
        respuesta = self.client.post(url, {
            'first_name': 'Ana', 'last_name': 'Torres', 'email': 'ana.torres@woof.ec', 'telefono': '+593987654321',
            'cedula': self.cliente.cedula, 'sector': '', 'rol': Roles.CLIENTE, 'is_active': 'on',
        })
        self.assertRedirects(respuesta, reverse('cuentas:usuarios'))
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.last_name, self.cliente.email), ('Torres', 'ana.torres@woof.ec'))

    def test_no_se_quita_su_propio_rol(self):
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.superadmin.pk]), {'rol': Roles.ADMINISTRADOR, 'is_active': 'on'},
        )
        self.assertContains(respuesta, 'No puedes quitarte el rol de superadministrador')
        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.rol, Roles.SUPERADMIN)

    def test_desactiva_y_reactiva_una_cuenta(self):
        url = reverse('cuentas:equipo_estado', args=[self.veterinario.pk])
        self.assertEqual(self.client.get(url).status_code, 405)   # solo POST
        self.client.post(url)
        self.veterinario.refresh_from_db()
        self.assertFalse(self.veterinario.is_active)
        self.client.post(url)
        self.veterinario.refresh_from_db()
        self.assertTrue(self.veterinario.is_active)

    def test_no_se_desactiva_a_si_mismo(self):
        self.client.post(reverse('cuentas:equipo_estado', args=[self.superadmin.pk]))
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_active)

    def test_cambia_la_contrasena_de_una_persona_del_equipo(self):
        respuesta = self.client.post(reverse('cuentas:equipo_contrasena', args=[self.veterinario.pk]), {
            'new_password1': 'Otra-clave-456', 'new_password2': 'Otra-clave-456',
        })
        self.assertRedirects(respuesta, reverse('cuentas:equipo'))
        self.veterinario.refresh_from_db()
        self.assertTrue(self.veterinario.check_password('Otra-clave-456'))


class AdministradorYSuperadminTests(TestCase):
    """El administrador gestiona clientes y veterinarios; a los demás administradores, solo el superadministrador."""

    def setUp(self):
        self.administrador = usuario_con_rol('jefa', Roles.ADMINISTRADOR, 1)
        self.otro_administrador = usuario_con_rol('pablo', Roles.ADMINISTRADOR, 2)
        self.superadmin = usuario_con_rol('sara', Roles.SUPERADMIN, 3)
        self.cliente = usuario_con_rol('ana', Roles.CLIENTE, 4)
        self.client.force_login(self.administrador)

    def test_no_edita_a_otro_administrador_ni_al_superadministrador(self):
        for persona in (self.otro_administrador, self.superadmin):
            with self.subTest(persona=persona.username):
                url = reverse('cuentas:usuario_editar', args=[persona.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {'rol': Roles.CLIENTE, 'is_active': 'on'}).status_code, 403)
                persona.refresh_from_db()
                self.assertNotEqual(persona.rol, Roles.CLIENTE)

    def test_no_puede_crear_administradores(self):
        respuesta = self.client.post(
            reverse('cuentas:usuario_editar', args=[self.cliente.pk]), {'rol': Roles.ADMINISTRADOR, 'is_active': 'on'},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('rol', respuesta.context['form'].errors)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rol, Roles.CLIENTE)

    def test_la_lista_solo_ofrece_editar_las_cuentas_que_gestiona(self):
        usuarios = {persona.username: persona.gestionable
                    for persona in self.client.get(reverse('cuentas:usuarios')).context['usuarios']}
        self.assertEqual(usuarios, {'jefa': True, 'pablo': False, 'sara': False, 'ana': True})

    def test_la_portada_del_administrador_revisa_servicios_y_horarios(self):
        pasos = self.client.get(reverse('panel:inicio_administrador')).context['pasos']
        self.assertEqual([paso['hecho'] for paso in pasos], [False, False, False])


class DestinoDespuesDelLoginTests(TestCase):
    """Si la página guardada en ?next= es de otro rol, el login lleva al panel de quien entra (no a una pantalla ajena)."""

    def setUp(self):
        self.veterinario = usuario_con_rol('dra.paredes', Roles.VETERINARIO, 1)
        self.cliente = usuario_con_rol('ana', Roles.CLIENTE, 2)

    def entrar(self, usuario, siguiente):
        return self.client.post(f"{reverse('cuentas:login')}?next={siguiente}",
                                {'username': usuario.username, 'password': 'Clave-segura-123'})

    @override_settings(DOBLE_FACTOR=False)
    def test_el_veterinario_no_cae_en_mis_mascotas(self):
        respuesta = self.entrar(self.veterinario, reverse('mascotas:lista'))
        self.assertRedirects(respuesta, reverse('panel:panel'), fetch_redirect_response=False)

    @override_settings(DOBLE_FACTOR=False)
    def test_el_cliente_si_vuelve_a_la_pagina_que_pidio(self):
        respuesta = self.entrar(self.cliente, reverse('mascotas:lista'))
        self.assertRedirects(respuesta, reverse('mascotas:lista'))

    @override_settings(DOBLE_FACTOR=False)
    def test_una_pagina_de_su_rol_si_se_respeta(self):
        respuesta = self.entrar(self.veterinario, reverse('citas:agenda'))
        self.assertRedirects(respuesta, reverse('citas:agenda'))

    def test_con_doble_factor_tambien_se_corrige_el_destino(self):
        self.entrar(self.veterinario, reverse('mascotas:lista'))
        self.assertEqual(self.client.session['pre_2fa_next'], reverse('panel:panel'))

    def test_otro_rol_en_mis_mascotas_vuelve_a_su_panel(self):
        self.client.force_login(self.veterinario)
        for nombre in ('mascotas:lista', 'mascotas:crear'):
            with self.subTest(pantalla=nombre):
                self.assertRedirects(self.client.get(reverse(nombre)), reverse('panel:panel'),
                                     fetch_redirect_response=False)

    def test_el_menu_de_la_portada_no_ofrece_mis_mascotas_al_veterinario(self):
        self.client.force_login(self.veterinario)
        respuesta = self.client.get(reverse('cuentas:inicio'))
        self.assertContains(respuesta, 'Mi panel')
        self.assertNotContains(respuesta, 'Mis mascotas</a>')


class ServiciosDeCuentasTests(TestCase):
    """Las reglas que salieron de las vistas, probadas directamente en los services."""

    def peticion_con_sesion(self):
        peticion = RequestFactory().get('/')
        SessionMiddleware(lambda request: None).process_request(peticion)
        peticion.user = AnonymousUser()
        return peticion

    def test_iniciar_y_completar_el_login_en_dos_pasos(self):
        usuario = crear_usuario()
        peticion = self.peticion_con_sesion()
        iniciar_login_pendiente(peticion, usuario, '/mascotas/')
        self.assertEqual(peticion.session['pre_2fa_user'], usuario.pk)
        self.assertEqual(len(mail.outbox), 1)                     # se envió el código al correo

        self.assertEqual(completar_login(peticion), '/mascotas/')  # devuelve a dónde ir
        self.assertEqual(peticion.user, usuario)                   # login() dejó la sesión iniciada
        self.assertNotIn('pre_2fa_user', peticion.session)

    def test_exigir_gestion(self):
        administrador = usuario_con_rol('admin', Roles.ADMINISTRADOR, 1)
        superadmin = usuario_con_rol('jefa', Roles.SUPERADMIN, 2)
        cliente = usuario_con_rol('luis', Roles.CLIENTE, 3)
        PoliticaDeCuentas.exigir_gestion(administrador, cliente)    # el administrador gestiona clientes
        with self.assertRaises(PermissionDenied):
            PoliticaDeCuentas.exigir_gestion(administrador, superadmin)
