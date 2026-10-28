import csv
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import BooleanField, ExpressionWrapper, Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from citas.models import Cita, EstadoCita, HorarioVeterinario, Servicio
from cuentas.forms import RegistroForm, UsuarioRolForm, VerificarCodigoForm
from cuentas.mixins import AdministradorRequeridoMixin, ClienteRequeridoMixin, VeterinarioRequeridoMixin
from cuentas.models import Roles
from cuentas.services import cancelar_login_pendiente, enviar_codigo, hay_login_pendiente, verificar_codigo
from mascotas.models import Especies, Mascota


class InicioView(TemplateView):
    template_name = 'cuentas/inicio.html'


class InicioClienteView(ClienteRequeridoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_cliente.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Solo las mascotas de quien inició sesión; sin los bytes de la foto, pero sabiendo si tiene una
        mascotas = list(
            Mascota.objects.filter(dueno=self.request.user)
            .defer('foto')
            .annotate(tiene_foto=ExpressionWrapper(Q(foto__isnull=False), output_field=BooleanField()))
        )
        # Qué tan completa está cada ficha: foto, raza, sexo, fecha de nacimiento y peso (datos reales)
        for mascota in mascotas:
            datos = [mascota.tiene_foto, mascota.raza, mascota.sexo, mascota.fecha_nacimiento, mascota.peso_kg]
            mascota.completa = round(sum(1 for dato in datos if dato) * 100 / len(datos))
        contexto['mascotas'] = mascotas
        contexto['especies'] = [(valor, nombre) for valor, nombre in Especies.choices
                                if any(m.especie == valor for m in mascotas)]

        # La semana actual (lunes a domingo) con hoy marcado, y las próximas citas (cuando exista Cita: hoy ninguna)
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        contexto['hoy'] = hoy
        contexto['semana'] = [lunes + timedelta(days=i) for i in range(7)]
        # Las próximas 4 citas confirmadas de sus mascotas, para la línea de tiempo
        contexto['proximas_citas'] = list(
            Cita.objects.filter(mascota__dueno=self.request.user, estado=EstadoCita.CONFIRMADA, inicio__gt=timezone.now())
            .select_related('mascota', 'servicio', 'veterinario')[:4]
        )
        # Para los accesos rápidos: la cita más cercana y cuántos servicios se pueden agendar
        contexto['proxima_cita'] = contexto['proximas_citas'][0] if contexto['proximas_citas'] else None
        contexto['servicios_disponibles'] = Servicio.objects.filter(activo=True, veterinarios__isnull=False).distinct().count()
        return contexto


class InicioVeterinarioView(VeterinarioRequeridoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_veterinario.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        ahora = timezone.localtime()
        hoy = ahora.date()
        if ahora.hour < 12:
            contexto['saludo'] = 'Buenos días'
        elif ahora.hour < 19:
            contexto['saludo'] = 'Buenas tardes'
        else:
            contexto['saludo'] = 'Buenas noches'

        # Período de las estadísticas: llega por ?periodo= (un valor inventado vuelve al de 7 días)
        periodos = {'7d': ('7 días', 7), 'mes': ('1 mes', 30), '3m': ('3 meses', 90)}
        clave = self.request.GET.get('periodo', '7d')
        if clave not in periodos:
            clave = '7d'
        dias = periodos[clave][1]
        contexto['periodos'] = [(valor, nombre) for valor, (nombre, _) in periodos.items()]
        contexto['periodo'] = clave

        # Período actual (los últimos N días, hasta hoy) y el anterior del mismo largo, para comparar
        desde = hoy - timedelta(days=dias - 1)
        desde_anterior = desde - timedelta(days=dias)
        mis_citas = Cita.objects.filter(veterinario=self.request.user).exclude(estado=EstadoCita.CANCELADA)
        del_periodo = mis_citas.filter(inicio__date__range=(desde, hoy))
        del_anterior = mis_citas.filter(inicio__date__range=(desde_anterior, desde - timedelta(days=1)))

        # Citas por día para el gráfico (las canceladas no cuentan: no ocuparon tiempo)
        fechas = [desde + timedelta(days=i) for i in range(dias)]
        por_dia = {fecha: 0 for fecha in fechas}
        for inicio in del_periodo.values_list('inicio', flat=True):
            por_dia[timezone.localtime(inicio).date()] += 1
        citas_por_dia = [por_dia[fecha] for fecha in fechas]

        # Ocupación: minutos con cita sobre los minutos de horario publicado en el período
        minutos_citas = sum((fin - inicio).total_seconds() / 60 for inicio, fin in del_periodo.values_list('inicio', 'fin'))
        minutos_horario = sum(
            (datetime.combine(hoy, fin) - datetime.combine(hoy, inicio)).total_seconds() / 60
            for inicio, fin in HorarioVeterinario.objects
            .filter(veterinario=self.request.user, fecha__range=(desde, hoy))
            .values_list('hora_inicio', 'hora_fin')
        )

        def contar(consulta, estado=None):
            return consulta.filter(estado=estado).count() if estado else consulta.count()

        contexto['estadisticas'] = {
            'citas': sum(citas_por_dia),
            'atendidas': contar(del_periodo, EstadoCita.ATENDIDA),
            'ocupacion': round(minutos_citas * 100 / minutos_horario) if minutos_horario else 0,
            'no_asistio': contar(del_periodo, EstadoCita.NO_ASISTIO),
            # suma del precio copiado en las citas atendidas del período
            'ganancias': del_periodo.filter(estado=EstadoCita.ATENDIDA).aggregate(total=Sum('precio'))['total'] or 0,
        }
        # Cambio frente al período anterior (sin datos anteriores no se inventa un porcentaje)
        contexto['variaciones'] = {
            'citas': variacion(contexto['estadisticas']['citas'], contar(del_anterior)),
            'atendidas': variacion(contexto['estadisticas']['atendidas'], contar(del_anterior, EstadoCita.ATENDIDA)),
            'no_asistio': variacion(contexto['estadisticas']['no_asistio'], contar(del_anterior, EstadoCita.NO_ASISTIO)),
        }
        contexto['servicios_que_atiendo'] = self.request.user.servicios.filter(activo=True).count()

        # Agenda de hoy: cada cita se ubica en la línea de tiempo por porcentaje (como la línea de "ahora")
        citas_de_hoy = list(
            Cita.objects.filter(veterinario=self.request.user, inicio__date=hoy)
            .exclude(estado=EstadoCita.CANCELADA)
            .select_related('mascota', 'servicio')
        )
        horas_en = [timezone.localtime(cita.inicio) for cita in citas_de_hoy]
        horas_fin = [timezone.localtime(cita.fin) for cita in citas_de_hoy]
        # De 08:00 a 18:00, o más si hay citas antes o después
        inicio_agenda = min([8] + [h.hour for h in horas_en])
        fin_agenda = max([18] + [h.hour + (1 if h.minute else 0) for h in horas_fin])
        largo = (fin_agenda - inicio_agenda) * 60

        def posicion(momento):
            return (momento.hour * 60 + momento.minute - inicio_agenda * 60) * 100 / largo

        contexto['citas_hoy'] = len(citas_de_hoy)
        contexto['citas_de_hoy'] = [
            {'cita': cita, 'arriba': posicion(inicio), 'alto': posicion(fin) - posicion(inicio)}
            for cita, inicio, fin in zip(citas_de_hoy, horas_en, horas_fin)
        ]
        contexto['agenda_inicio'], contexto['agenda_fin'] = inicio_agenda, fin_agenda
        contexto['horas_agenda'] = [f'{hora:02d}:00' for hora in range(inicio_agenda, fin_agenda)]
        contexto['grafico'] = grafico_de_linea(fechas, citas_por_dia)
        return contexto


def grafico_de_linea(fechas, valores, ancho=1000, alto=210):
    """Arma en el servidor el SVG del gráfico de citas por día: la línea, el área, las guías y las etiquetas."""
    izquierda, derecha, arriba, abajo = 44, 16, 16, 34
    maximo = max(4, max(valores))                       # con 0 citas, el eje igual llega a 4 (se ve la línea en 0)
    paso_x = (ancho - izquierda - derecha) / max(len(valores) - 1, 1)
    alto_util = alto - arriba - abajo

    def punto(i, valor):
        return izquierda + i * paso_x, arriba + alto_util * (1 - valor / maximo)

    puntos = [punto(i, valor) for i, valor in enumerate(valores)]
    linea = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in puntos)
    area = f'{linea} L {puntos[-1][0]:.1f} {arriba + alto_util:.1f} L {puntos[0][0]:.1f} {arriba + alto_util:.1f} Z'
    guias = [{'y': round(arriba + alto_util * (1 - n / 4), 1), 'texto': round(maximo * n / 4)} for n in range(5)]
    cada = max(1, round(len(fechas) / 6))              # unas 6 o 7 fechas en el eje, sin amontonarlas
    etiquetas = [
        {'x': round(punto(i, 0)[0], 1), 'fecha': fecha}
        for i, fecha in enumerate(fechas) if i % cada == 0 or i == len(fechas) - 1
    ]
    return {'ancho': ancho, 'alto': alto, 'linea': linea, 'area': area, 'guias': guias, 'etiquetas': etiquetas,
            'base': arriba + alto_util, 'izquierda': izquierda, 'derecha': ancho - derecha}


class InicioAdministradorView(AdministradorRequeridoMixin, TemplateView):
    template_name = 'cuentas/panel/inicio_administrador.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuarios = get_user_model().objects
        hoy = timezone.localdate()

        # Período: ?periodo= (un valor inventado vuelve al de 1 mes)
        periodos = {'7d': ('7 días', 7), 'mes': ('1 mes', 30), '3m': ('3 meses', 90), '6m': ('6 meses', 180)}
        clave = self.request.GET.get('periodo', 'mes')
        if clave not in periodos:
            clave = 'mes'
        dias = periodos[clave][1]
        contexto['periodos'] = [(valor, nombre) for valor, (nombre, _) in periodos.items()]
        contexto['periodo'] = clave

        # Período actual y el anterior, del mismo largo, para comparar
        desde = hoy - timedelta(days=dias - 1)
        desde_anterior = desde - timedelta(days=dias)

        def en_rango(consulta, campo, inicio, fin):
            return consulta.filter(**{f'{campo}__date__gte': inicio, f'{campo}__date__lte': fin}).count()

        nuevas = en_rango(usuarios.all(), 'date_joined', desde, hoy)
        nuevas_antes = en_rango(usuarios.all(), 'date_joined', desde_anterior, desde - timedelta(days=1))
        mascotas = en_rango(Mascota.objects.all(), 'creado', desde, hoy)
        mascotas_antes = en_rango(Mascota.objects.all(), 'creado', desde_anterior, desde - timedelta(days=1))
        contexto['cifras'] = [
            {'etiqueta': 'Cuentas nuevas', 'icono': 'bi-person-plus', 'valor': nuevas,
             'variacion': variacion(nuevas, nuevas_antes)},
            {'etiqueta': 'Mascotas registradas', 'icono': 'bi-heart', 'valor': mascotas,
             'variacion': variacion(mascotas, mascotas_antes)},
            {'etiqueta': 'Clientes', 'icono': 'bi-people', 'valor': usuarios.filter(rol=Roles.CLIENTE).count(),
             'variacion': None},
            {'etiqueta': 'Veterinarios', 'icono': 'bi-heart-pulse', 'valor': usuarios.filter(rol=Roles.VETERINARIO).count(),
             'variacion': None},
        ]

        # Gráfico: cuentas nuevas por día del período (datos reales)
        fechas = [desde + timedelta(days=i) for i in range(dias)]
        por_dia = {fecha: 0 for fecha in fechas}
        for unido in usuarios.filter(date_joined__date__gte=desde).values_list('date_joined', flat=True):
            fecha = timezone.localtime(unido).date()
            if fecha in por_dia:
                por_dia[fecha] += 1
        contexto['grafico'] = grafico_de_linea(fechas, list(por_dia.values()))
        contexto['nuevas_periodo'] = nuevas

        # Cuentas por rol (para la barra de reparto)
        total = usuarios.count()
        contexto['total_usuarios'] = total
        contexto['por_rol'] = [
            {'nombre': nombre, 'valor': usuarios.filter(rol=valor).count(), 'clase': valor}
            for valor, nombre in Roles.choices
        ]
        for rol in contexto['por_rol']:
            rol['porcentaje'] = round(rol['valor'] * 100 / total) if total else 0
        contexto['total_mascotas'] = Mascota.objects.count()
        contexto['total_veterinarios'] = contexto['cifras'][3]['valor']

        # ¿La clínica ya puede recibir citas? Servicios y horarios llegan con la app citas: por ahora pendientes.
        pasos = [
            {'titulo': 'Registrar a los veterinarios', 'hecho': contexto['total_veterinarios'] > 0},
            {'titulo': 'Crear los servicios', 'hecho': False},
            {'titulo': 'Publicar los horarios', 'hecho': False},
        ]
        contexto['pasos'] = pasos
        contexto['pasos_hechos'] = sum(paso['hecho'] for paso in pasos)
        contexto['avance'] = round(contexto['pasos_hechos'] * 100 / len(pasos))

        contexto['recientes'] = usuarios.order_by('-date_joined')[:8]
        return contexto


def variacion(actual, anterior):
    """Cambio frente al período anterior. Sin datos para comparar no se inventa un porcentaje."""
    if anterior == 0:
        return {'texto': f'+{actual} nuevas' if actual else '—', 'tipo': 'nuevo' if actual else 'neutro'}
    cambio = (actual - anterior) * 100 / anterior
    return {'texto': f'{abs(cambio):.1f}%'.replace('.', ','), 'tipo': 'sube' if cambio > 0 else 'baja' if cambio < 0 else 'neutro'}


class ReporteUsuariosView(AdministradorRequeridoMixin, View):
    """Descarga las cuentas en CSV (sin contraseñas): lo que hace el botón "Descargar reporte"."""

    def get(self, request):
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = f'attachment; filename="woof-cuentas-{timezone.localdate():%Y-%m-%d}.csv"'
        respuesta.write('\ufeff')   # para que Excel lea bien las tildes
        escritor = csv.writer(respuesta)
        escritor.writerow(['Usuario', 'Nombre', 'Correo', 'Rol', 'Cédula', 'Teléfono', 'Activa', 'Registro'])
        for persona in get_user_model().objects.order_by('date_joined'):
            escritor.writerow([
                persona.username, persona.get_full_name(), persona.email, persona.get_rol_display(),
                persona.cedula, persona.telefono, 'Sí' if persona.is_active else 'No',
                timezone.localtime(persona.date_joined).strftime('%Y-%m-%d %H:%M'),
            ])
        return respuesta


class UsuarioListView(AdministradorRequeridoMixin, ListView):
    """Usuarios de la clínica para el administrador: buscador y filtro por rol (reemplaza al admin de Django)."""
    template_name = 'cuentas/panel/usuarios.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        usuarios = get_user_model().objects.order_by('-date_joined')
        buscar = self.request.GET.get('q', '').strip()
        if buscar:
            usuarios = usuarios.filter(
                Q(username__icontains=buscar) | Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar)
                | Q(email__icontains=buscar) | Q(cedula__icontains=buscar)
            )
        rol = self.request.GET.get('rol', '')
        if rol in Roles.values:  # un rol inventado en la URL se ignora
            usuarios = usuarios.filter(rol=rol)
        return usuarios

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['buscar'] = self.request.GET.get('q', '').strip()
        contexto['rol_elegido'] = self.request.GET.get('rol', '')
        contexto['roles'] = Roles.choices
        return contexto


class UsuarioEditarView(AdministradorRequeridoMixin, SuccessMessageMixin, UpdateView):
    """Cambiar el rol de una cuenta (por ejemplo, darle el rol de veterinario) o desactivarla."""
    model = get_user_model()
    form_class = UsuarioRolForm
    template_name = 'cuentas/panel/usuario_editar.html'
    context_object_name = 'persona'
    success_url = reverse_lazy('cuentas:usuarios')
    success_message = 'Se guardaron los cambios de %(persona)s.'

    def form_valid(self, form):
        # El administrador no puede quitarse su propio rol ni desactivarse: se quedaría sin acceso al panel
        if self.object.pk == self.request.user.pk and (
            form.cleaned_data['rol'] != Roles.ADMINISTRADOR or not form.cleaned_data['is_active']
        ):
            form.add_error(None, 'No puedes quitarte el rol de administrador ni desactivar tu propia cuenta.')
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_message(self, cleaned_data):
        return self.success_message % {'persona': self.object}


class PanelView(LoginRequiredMixin, View):
    """Después del login, manda a cada usuario a la portada de su rol. No dibuja nada: solo redirige."""

    def get(self, request):
        if request.user.es_veterinario:
            return redirect('cuentas:inicio_veterinario')
        if request.user.es_administrador:
            return redirect('cuentas:inicio_administrador')
        return redirect('cuentas:inicio_cliente')  # el cliente es el rol por defecto


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = 'cuentas/registro.html'
    success_url = reverse_lazy('cuentas:login')


class LoginDosPasosView(LoginView):
    """Primer paso del login: valida usuario y contraseña, pero en vez de iniciar sesión envía un código al correo."""
    template_name = 'cuentas/login.html'

    def get(self, request, *args, **kwargs):
        # Volver al login (por ejemplo, con "Cancelar") empieza de cero: se descarta el login a medias
        cancelar_login_pendiente(request)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # Con el doble factor apagado (Render), LoginView inicia sesión directo y va a ?next= o al panel
        if not settings.DOBLE_FACTOR:
            return super().form_valid(form)

        usuario = form.get_user()
        self.request.session['pre_2fa_user'] = usuario.pk           # la sesión es JSON: se guarda el pk, no el objeto
        self.request.session['pre_2fa_next'] = self.get_success_url()  # a dónde ir al terminar (respeta ?next=)
        enviar_codigo(self.request, usuario)
        return redirect('cuentas:verificar')


class VerificarView(FormView):
    template_name = 'cuentas/verificar.html'
    form_class = VerificarCodigoForm

    def dispatch(self, request, *args, **kwargs):
        # Solo se entra si se acaba de pasar la contraseña y el código sigue vigente (como LoginRequiredMixin en mascotas)
        if not hay_login_pendiente(request):
            cancelar_login_pendiente(request)
            return redirect('cuentas:login')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # El formulario ya validó el formato (6 dígitos); aquí se comprueba si el código es el correcto.
        if not verificar_codigo(self.request, form.cleaned_data['codigo']):
            form.add_error('codigo', 'El código es incorrecto o ya venció.')
            return self.form_invalid(form)

        # Se sacan de la sesión antes del login(), que cambia la llave de la sesión por seguridad
        pk = self.request.session.pop('pre_2fa_user')
        siguiente = self.request.session.pop('pre_2fa_next', '/')

        usuario = get_user_model().objects.get(pk=pk)
        login(self.request, usuario)
        return redirect(siguiente)
