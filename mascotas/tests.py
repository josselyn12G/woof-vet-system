from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from cuentas.models import Usuario

from .forms import MascotaForm
from .models import Especies, Mascota


def crear_usuario(username='ana', **datos):
    """Crea un usuario válido; el correo se arma con el username para poder crear varios."""
    valores = {
        'username': username,
        'email': f'{username}@woof.ec',
        'telefono': '+593987654321',
        'password': 'Clave-segura-123',
    }
    valores.update(datos)
    return Usuario.objects.create_user(**valores)


def crear_mascota(dueno, **datos):
    valores = {'nombre': 'Firulais', 'especie': Especies.PERRO}
    valores.update(datos)
    return Mascota.objects.create(dueno=dueno, **valores)


def crear_foto(nombre='foto.png', formato='PNG', tamano=(10, 10), relleno=0):
    """Imagen real hecha con Pillow; "relleno" agrega bytes para simular un archivo pesado."""
    archivo = BytesIO()
    Image.new('RGB', tamano, 'orange').save(archivo, formato)
    return SimpleUploadedFile(nombre, archivo.getvalue() + b'0' * relleno, content_type=f'image/{formato.lower()}')


def datos_validos(**cambios):
    """Datos del formulario que pasan todas las validaciones."""
    datos = {
        'nombre': 'Michi',
        'especie': 'gato',
        'raza': 'Siamés',
        'sexo': 'H',
        'fecha_nacimiento': '2022-03-15',
        'peso_kg': '4.20',
    }
    datos.update(cambios)
    return datos


class MascotaModelTests(TestCase):
    def setUp(self):
        self.ana = crear_usuario()

    def test_str_devuelve_el_nombre(self):
        self.assertEqual(str(crear_mascota(self.ana)), 'Firulais')

    def test_las_mascotas_quedan_en_el_usuario(self):
        crear_mascota(self.ana)
        # related_name='mascotas' permite usuario.mascotas.all()
        self.assertEqual(self.ana.mascotas.count(), 1)

    def test_edad_sin_fecha_es_none(self):
        self.assertIsNone(crear_mascota(self.ana).edad)

    def test_edad_en_anios(self):
        hoy = timezone.localdate()
        mascota = crear_mascota(self.ana, fecha_nacimiento=date(hoy.year - 2, hoy.month, 1))
        self.assertEqual(mascota.edad, '2 años')

    def test_edad_menor_a_un_mes(self):
        mascota = crear_mascota(self.ana, fecha_nacimiento=timezone.localdate())
        self.assertEqual(mascota.edad, 'Menos de un mes')

    def test_fecha_futura_no_es_valida(self):
        mascota = Mascota(dueno=self.ana, nombre='Max', especie='perro',
                          fecha_nacimiento=timezone.localdate() + timedelta(days=1))
        with self.assertRaises(ValidationError) as error:
            mascota.full_clean()
        self.assertIn('fecha_nacimiento', error.exception.message_dict)

    def test_la_base_rechaza_peso_cero(self):
        # create() no ejecuta los validadores de Django: solo la CheckConstraint lo detiene.
        with self.assertRaises(IntegrityError):
            crear_mascota(self.ana, peso_kg=Decimal('0'))

    def test_la_base_rechaza_una_especie_invalida(self):
        crear_mascota(self.ana)
        with self.assertRaises(IntegrityError):
            Mascota.objects.update(especie='dragon')


class MascotaFormTests(TestCase):
    def test_formulario_valido(self):
        self.assertTrue(MascotaForm(data=datos_validos()).is_valid())

    def test_los_datos_necesarios_son_obligatorios(self):
        form = MascotaForm(data={})
        self.assertFalse(form.is_valid())
        for campo in ('nombre', 'especie', 'sexo', 'fecha_nacimiento', 'peso_kg'):
            with self.subTest(campo=campo):
                self.assertIn(campo, form.errors)
        self.assertIn('Escribe el nombre de tu mascota.', form.errors['nombre'])

    def test_la_raza_es_opcional(self):
        self.assertTrue(MascotaForm(data=datos_validos(raza='')).is_valid())

    def test_el_nombre_quita_espacios_de_mas(self):
        form = MascotaForm(data=datos_validos(nombre='  Señor   Bigotes '))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['nombre'], 'Señor Bigotes')

    def test_el_nombre_solo_acepta_letras(self):
        for nombre in ('M', '123', 'Max!!', '   '):
            with self.subTest(nombre=nombre):
                form = MascotaForm(data=datos_validos(nombre=nombre))
                self.assertFalse(form.is_valid())
                self.assertIn('nombre', form.errors)

    def test_la_raza_solo_acepta_letras(self):
        form = MascotaForm(data=datos_validos(raza='Siamés 2'))
        self.assertFalse(form.is_valid())
        self.assertIn('raza', form.errors)

    def test_no_se_repite_el_nombre_entre_mis_mascotas(self):
        ana = crear_usuario()
        crear_mascota(ana, nombre='Michi')
        form = MascotaForm(data=datos_validos(nombre='michi'), dueno=ana)
        self.assertFalse(form.is_valid())
        self.assertIn('Ya tienes una mascota llamada michi.', form.errors['nombre'])
        # Otro cliente sí puede usar el mismo nombre
        self.assertTrue(MascotaForm(data=datos_validos(), dueno=crear_usuario('luis')).is_valid())

    def test_editar_puede_conservar_su_propio_nombre(self):
        ana = crear_usuario()
        michi = crear_mascota(ana, nombre='Michi')
        self.assertTrue(MascotaForm(data=datos_validos(), instance=michi, dueno=ana).is_valid())

    def test_peso_tiene_un_maximo(self):
        form = MascotaForm(data=datos_validos(peso_kg='150.01'))
        self.assertFalse(form.is_valid())
        self.assertIn('peso_kg', form.errors)

    def test_fecha_de_nacimiento_demasiado_antigua(self):
        form = MascotaForm(data=datos_validos(fecha_nacimiento='1950-01-01'))
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_nacimiento', form.errors)

    def test_peso_debe_ser_mayor_que_cero(self):
        for peso in ('0', '-3'):
            form = MascotaForm(data=datos_validos(peso_kg=peso))
            self.assertFalse(form.is_valid())
            self.assertIn('peso_kg', form.errors)

    def test_fecha_de_nacimiento_no_puede_ser_futura(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        form = MascotaForm(data=datos_validos(fecha_nacimiento=manana))
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_nacimiento', form.errors)

    def test_el_dueno_no_esta_en_el_formulario(self):
        self.assertNotIn('dueno', MascotaForm().fields)


class AccesoSinSesionTests(TestCase):
    """HU-05: todas las URLs del CRUD redirigen al login si no hay sesión."""

    def test_todas_las_urls_piden_iniciar_sesion(self):
        mascota = crear_mascota(crear_usuario())
        urls = [
            reverse('mascotas:lista'),
            reverse('mascotas:crear'),
            reverse('mascotas:detalle', args=[mascota.pk]),
            reverse('mascotas:editar', args=[mascota.pk]),
            reverse('mascotas:eliminar', args=[mascota.pk]),
            reverse('mascotas:carnet', args=[mascota.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(respuesta, f"{reverse('cuentas:login')}?next={url}")

    def test_eliminar_con_post_sin_sesion_no_borra(self):
        mascota = crear_mascota(crear_usuario())
        respuesta = self.client.post(reverse('mascotas:eliminar', args=[mascota.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Mascota.objects.filter(pk=mascota.pk).exists())


class MascotaViewTests(TestCase):
    def setUp(self):
        self.ana = crear_usuario('ana')
        self.luis = crear_usuario('luis')
        self.firulais = crear_mascota(self.ana, nombre='Firulais')
        self.mascota_de_luis = crear_mascota(self.luis, nombre='Rocky')
        # force_login inicia sesión directo, sin pasar por el código de doble factor
        self.client.force_login(self.ana)

    # ----- HU-07: ver mis mascotas -----
    def test_lista_muestra_solo_mis_mascotas(self):
        respuesta = self.client.get(reverse('mascotas:lista'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'mascotas/lista.html')
        self.assertContains(respuesta, 'Firulais')
        self.assertNotContains(respuesta, 'Rocky')

    def test_cada_tarjeta_tiene_sus_botones(self):
        respuesta = self.client.get(reverse('mascotas:lista'))
        for nombre in ('detalle', 'carnet', 'editar', 'eliminar'):
            with self.subTest(boton=nombre):
                self.assertContains(respuesta, reverse(f'mascotas:{nombre}', args=[self.firulais.pk]))
        self.assertContains(respuesta, 'Ver ficha completa')

    def test_lista_vacia_invita_a_registrar(self):
        self.firulais.delete()
        respuesta = self.client.get(reverse('mascotas:lista'))
        self.assertContains(respuesta, 'Aún no tienes mascotas registradas')
        self.assertContains(respuesta, reverse('mascotas:crear'))

    # ----- HU-06: registrar una mascota -----
    def test_crear_asigna_el_dueno_y_redirige_al_detalle(self):
        # Aunque alguien envíe "dueno" a mano, el formulario lo ignora: se usa request.user
        respuesta = self.client.post(reverse('mascotas:crear'), datos_validos(dueno=self.luis.pk), follow=True)
        michi = Mascota.objects.get(nombre='Michi')
        self.assertEqual(michi.dueno, self.ana)
        self.assertRedirects(respuesta, reverse('mascotas:detalle', args=[michi.pk]))
        self.assertContains(respuesta, 'Michi se registró correctamente.')

    def test_crear_con_nombre_repetido_no_guarda(self):
        respuesta = self.client.post(reverse('mascotas:crear'), datos_validos(nombre='Firulais'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya tienes una mascota llamada Firulais.')
        self.assertEqual(Mascota.objects.filter(dueno=self.ana).count(), 1)

    def test_crear_con_errores_no_guarda(self):
        respuesta = self.client.post(reverse('mascotas:crear'), datos_validos(nombre='', peso_kg='0'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Mascota.objects.filter(especie='gato').exists())
        self.assertContains(respuesta, 'is-invalid')

    # ----- HU-08: ver el detalle -----
    def test_detalle_muestra_los_datos_y_la_edad(self):
        hoy = timezone.localdate()
        self.firulais.fecha_nacimiento = date(hoy.year - 3, hoy.month, 1)
        self.firulais.save()
        respuesta = self.client.get(reverse('mascotas:detalle', args=[self.firulais.pk]))
        self.assertContains(respuesta, 'Firulais')
        self.assertContains(respuesta, '3 años')

    def test_detalle_de_mascota_ajena_da_404(self):
        respuesta = self.client.get(reverse('mascotas:detalle', args=[self.mascota_de_luis.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_detalle_inexistente_da_404(self):
        respuesta = self.client.get(reverse('mascotas:detalle', args=[999]))
        self.assertEqual(respuesta.status_code, 404)

    # ----- HU-09: editar -----
    def test_editar_muestra_los_datos_actuales(self):
        respuesta = self.client.get(reverse('mascotas:editar', args=[self.firulais.pk]))
        self.assertContains(respuesta, 'value="Firulais"')

    def test_editar_cambia_los_datos(self):
        respuesta = self.client.post(
            reverse('mascotas:editar', args=[self.firulais.pk]),
            datos_validos(nombre='Max', especie='perro'),
            follow=True,
        )
        self.firulais.refresh_from_db()
        self.assertEqual(self.firulais.nombre, 'Max')
        self.assertEqual(self.firulais.dueno, self.ana)
        self.assertContains(respuesta, 'Los datos de Max se actualizaron.')

    def test_editar_aplica_las_mismas_validaciones(self):
        respuesta = self.client.post(
            reverse('mascotas:editar', args=[self.firulais.pk]), datos_validos(nombre='', peso_kg='-1'),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('nombre', respuesta.context['form'].errors)
        self.assertIn('peso_kg', respuesta.context['form'].errors)
        # El título sigue mostrando el nombre guardado, no el texto vacío que se envió
        self.assertContains(respuesta, 'Editar a Firulais')
        self.firulais.refresh_from_db()
        self.assertEqual(self.firulais.nombre, 'Firulais')

    def test_editar_mascota_ajena_da_404(self):
        url = reverse('mascotas:editar', args=[self.mascota_de_luis.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, datos_validos(nombre='Robado')).status_code, 404)
        self.mascota_de_luis.refresh_from_db()
        self.assertEqual(self.mascota_de_luis.nombre, 'Rocky')

    # ----- HU-10: eliminar -----
    def test_eliminar_pide_confirmacion_con_get(self):
        respuesta = self.client.get(reverse('mascotas:eliminar', args=[self.firulais.pk]))
        self.assertContains(respuesta, '¿Eliminar a Firulais?')
        self.assertTrue(Mascota.objects.filter(pk=self.firulais.pk).exists())

    def test_eliminar_borra_con_post(self):
        respuesta = self.client.post(reverse('mascotas:eliminar', args=[self.firulais.pk]), follow=True)
        self.assertRedirects(respuesta, reverse('mascotas:lista'))
        self.assertFalse(Mascota.objects.filter(pk=self.firulais.pk).exists())
        self.assertContains(respuesta, 'Firulais se eliminó.')

    def test_eliminar_mascota_ajena_da_404(self):
        url = reverse('mascotas:eliminar', args=[self.mascota_de_luis.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Mascota.objects.filter(pk=self.mascota_de_luis.pk).exists())

    # ----- HU-36: carnet de vacunación -----
    def test_carnet_muestra_la_mascota(self):
        respuesta = self.client.get(reverse('mascotas:carnet', args=[self.firulais.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'mascotas/carnet.html')
        self.assertContains(respuesta, 'Carnet de vacunación')
        self.assertContains(respuesta, 'Aún no hay vacunas registradas')

    def test_detalle_enlaza_al_carnet(self):
        respuesta = self.client.get(reverse('mascotas:detalle', args=[self.firulais.pk]))
        self.assertContains(respuesta, reverse('mascotas:carnet', args=[self.firulais.pk]))

    def test_carnet_de_mascota_ajena_da_404(self):
        respuesta = self.client.get(reverse('mascotas:carnet', args=[self.mascota_de_luis.pk]))
        self.assertEqual(respuesta.status_code, 404)

    # ----- HU-01: el menú enlaza a Mis mascotas -----
    def test_el_menu_muestra_mis_mascotas_con_sesion(self):
        respuesta = self.client.get(reverse('cuentas:inicio'))
        self.assertContains(respuesta, 'Mis mascotas')



class FotoMascotaTests(TestCase):
    def setUp(self):
        self.ana = crear_usuario()
        self.client.force_login(self.ana)

    def crear_con_foto(self, **datos):
        self.client.post(reverse('mascotas:crear'), datos_validos(foto=crear_foto(**datos)))
        return Mascota.objects.get(nombre='Michi')

    def test_la_foto_es_opcional(self):
        self.client.post(reverse('mascotas:crear'), datos_validos())
        self.assertIsNone(Mascota.objects.get(nombre='Michi').foto)

    def test_la_foto_se_guarda_en_la_base_reducida_a_webp(self):
        michi = self.crear_con_foto(tamano=(2000, 1000))
        imagen = Image.open(BytesIO(bytes(michi.foto)))
        self.assertEqual(imagen.format, 'WEBP')
        self.assertEqual(imagen.size, (800, 400))  # el lado mayor queda en 800 px, sin deformarse

    def test_el_detalle_muestra_la_foto(self):
        michi = self.crear_con_foto()
        respuesta = self.client.get(reverse('mascotas:detalle', args=[michi.pk]))
        self.assertContains(respuesta, reverse('mascotas:foto', args=[michi.pk]))

    def test_la_url_de_la_foto_entrega_la_imagen(self):
        michi = self.crear_con_foto()
        respuesta = self.client.get(reverse('mascotas:foto', args=[michi.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'image/webp')
        self.assertEqual(respuesta.content, bytes(michi.foto))

    def test_acepta_jpg_y_webp(self):
        for nombre, formato in (('foto.jpg', 'JPEG'), ('foto.webp', 'WEBP')):
            with self.subTest(formato=formato):
                form = MascotaForm(data=datos_validos(), files={'foto': crear_foto(nombre, formato)})
                self.assertTrue(form.is_valid(), form.errors)

    def test_rechaza_formatos_no_permitidos(self):
        form = MascotaForm(data=datos_validos(), files={'foto': crear_foto('foto.gif', 'GIF')})
        self.assertFalse(form.is_valid())
        self.assertIn('foto', form.errors)

    def test_rechaza_un_archivo_que_no_es_imagen(self):
        texto = SimpleUploadedFile('foto.png', b'esto no es una imagen', content_type='image/png')
        form = MascotaForm(data=datos_validos(), files={'foto': texto})
        self.assertFalse(form.is_valid())
        self.assertIn('foto', form.errors)

    def test_rechaza_fotos_de_mas_de_5_mb(self):
        form = MascotaForm(data=datos_validos(), files={'foto': crear_foto(relleno=5 * 1024 * 1024)})
        self.assertFalse(form.is_valid())
        self.assertIn('La foto no puede pesar más de 5 MB.', form.errors['foto'])

    def test_editar_sin_subir_otra_conserva_la_foto(self):
        michi = self.crear_con_foto()
        foto_original = bytes(michi.foto)
        respuesta = self.client.get(reverse('mascotas:editar', args=[michi.pk]))
        self.assertContains(respuesta, 'Quitar la foto actual')
        self.assertContains(respuesta, 'enctype="multipart/form-data"')

        self.client.post(reverse('mascotas:editar', args=[michi.pk]), datos_validos(raza='Persa'))
        michi.refresh_from_db()
        self.assertEqual(michi.raza, 'Persa')
        self.assertEqual(bytes(michi.foto), foto_original)

    def test_editar_puede_cambiar_la_foto(self):
        michi = self.crear_con_foto(tamano=(10, 10))
        self.client.post(reverse('mascotas:editar', args=[michi.pk]), datos_validos(foto=crear_foto(tamano=(50, 20))))
        michi.refresh_from_db()
        self.assertEqual(Image.open(BytesIO(bytes(michi.foto))).size, (50, 20))

    def test_editar_puede_quitar_la_foto(self):
        michi = self.crear_con_foto()
        self.client.post(reverse('mascotas:editar', args=[michi.pk]), datos_validos(quitar_foto='on'))
        michi.refresh_from_db()
        self.assertIsNone(michi.foto)

    def test_la_casilla_quitar_no_aparece_si_no_hay_foto(self):
        self.client.post(reverse('mascotas:crear'), datos_validos())
        michi = Mascota.objects.get(nombre='Michi')
        respuesta = self.client.get(reverse('mascotas:editar', args=[michi.pk]))
        self.assertNotContains(respuesta, 'Quitar la foto actual')

    def test_foto_de_mascota_ajena_da_404(self):
        michi = self.crear_con_foto()
        self.client.force_login(crear_usuario('luis'))
        self.assertEqual(self.client.get(reverse('mascotas:foto', args=[michi.pk])).status_code, 404)

    def test_un_administrador_puede_ver_la_foto(self):
        michi = self.crear_con_foto()
        self.client.force_login(crear_usuario('admin', is_staff=True))
        self.assertEqual(self.client.get(reverse('mascotas:foto', args=[michi.pk])).status_code, 200)

    def test_la_foto_pide_iniciar_sesion(self):
        michi = self.crear_con_foto()
        self.client.logout()
        url = reverse('mascotas:foto', args=[michi.pk])
        self.assertRedirects(self.client.get(url), f"{reverse('cuentas:login')}?next={url}")

    def test_mascota_sin_foto_da_404(self):
        self.client.post(reverse('mascotas:crear'), datos_validos())
        michi = Mascota.objects.get(nombre='Michi')
        self.assertEqual(self.client.get(reverse('mascotas:foto', args=[michi.pk])).status_code, 404)
