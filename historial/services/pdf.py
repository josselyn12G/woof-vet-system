"""
La historia clínica de una mascota en PDF, con el formato de Woof: franja naranja con el logo arriba, la ficha del
paciente, el resumen, el carnet de vacunas y cada consulta con su receta; pie café con la página y la fecha.
Se arma con ReportLab (platypus): bloques que se acomodan solos en las páginas.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.staticfiles import finders
from django.utils import timezone
from django.utils.formats import date_format
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .historial import HistorialService

# Los colores de la marca (los mismos del sitio)
NARANJA = colors.HexColor('#ee9a35')
NARANJA_SUAVE = colors.HexColor('#fdebd3')
CAFE = colors.HexColor('#573f33')
CAFE_TEXTO = colors.HexColor('#5b4a40')
GRIS = colors.HexColor('#8a7a70')
LINEA = colors.HexColor('#eadfd6')
ESTADOS = {
    'al_dia': (colors.HexColor('#e7f5ec'), colors.HexColor('#1e7b45')),
    'proxima': (colors.HexColor('#fdf1e3'), colors.HexColor('#9a5b00')),
    'vencida': (colors.HexColor('#fdecee'), colors.HexColor('#b4232a')),
    'reforzada': (colors.HexColor('#f3eeea'), GRIS),
}

MARGEN = 16 * mm
ALTO_CABECERA = 26 * mm
ALTO_PIE = 12 * mm

ESTILOS = {
    'titulo': ParagraphStyle('titulo', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=CAFE),
    'bajada': ParagraphStyle('bajada', fontName='Helvetica', fontSize=9.5, leading=13, textColor=GRIS),
    'seccion': ParagraphStyle('seccion', fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=CAFE,
                              spaceBefore=10, spaceAfter=6),
    'texto': ParagraphStyle('texto', fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=CAFE_TEXTO),
    'etiqueta': ParagraphStyle('etiqueta', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=GRIS),
    'dato': ParagraphStyle('dato', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=CAFE),
    'cifra': ParagraphStyle('cifra', fontName='Helvetica-Bold', fontSize=20, leading=22, textColor=CAFE),
    'consulta': ParagraphStyle('consulta', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=CAFE),
    'celda': ParagraphStyle('celda', fontName='Helvetica', fontSize=8.5, leading=11, textColor=CAFE_TEXTO),
    'celda_negrita': ParagraphStyle('celda_negrita', fontName='Helvetica-Bold', fontSize=8.5, leading=11,
                                    textColor=CAFE),
    'derecha': ParagraphStyle('derecha', fontName='Helvetica', fontSize=8.5, leading=11, textColor=GRIS,
                              alignment=TA_RIGHT),
}


def texto(valor, estilo='texto'):
    """Un párrafo con el texto escapado (un diagnóstico con < o & no rompe el PDF) y los saltos de línea."""
    return Paragraph(escape(str(valor or '—')).replace('\n', '<br/>'), ESTILOS[estilo])


def fecha(valor, formato='j \\d\\e F \\d\\e Y'):
    return date_format(timezone.localtime(valor) if hasattr(valor, 'tzinfo') and valor.tzinfo else valor, formato)


class PaginaNumerada(canvas.Canvas):
    """Dibuja la cabecera y el pie en cada página al final, cuando ya se sabe cuántas páginas hay ("1 de 3")."""

    def __init__(self, *args, mascota=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mascota = mascota
        self.paginas = []

    def showPage(self):
        self.paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.paginas)
        for estado in self.paginas:
            self.__dict__.update(estado)
            self.dibujar_marco(total)
            super().showPage()
        super().save()

    def dibujar_marco(self, total):
        ancho, alto = A4
        # Cabecera: franja naranja con el logo y el nombre de la mascota
        self.setFillColor(NARANJA)
        self.rect(0, alto - ALTO_CABECERA, ancho, ALTO_CABECERA, stroke=0, fill=1)
        logo = finders.find('img/logo-blanco.png')
        if logo:
            self.drawImage(logo, MARGEN, alto - ALTO_CABECERA + 7 * mm, width=30 * mm, height=12 * mm,
                           preserveAspectRatio=True, anchor='w', mask='auto')
        self.setFillColor(colors.white)
        self.setFont('Helvetica-Bold', 12)
        self.drawRightString(ancho - MARGEN, alto - 13 * mm, 'Historia clínica')
        self.setFont('Helvetica', 9)
        self.drawRightString(ancho - MARGEN, alto - 18.5 * mm, self.mascota or '')
        # Pie: franja café con la clínica, la página y la fecha en que se generó
        self.setFillColor(CAFE)
        self.rect(0, 0, ancho, ALTO_PIE, stroke=0, fill=1)
        self.setFillColor(colors.HexColor('#f5e9df'))
        self.setFont('Helvetica', 8)
        self.drawString(MARGEN, 4.5 * mm, 'Woof · Sistema veterinario · Documento informativo para el dueño de la mascota')
        hoy = date_format(timezone.localtime(), 'j/m/Y H:i')
        self.drawRightString(ancho - MARGEN, 4.5 * mm, f'Página {self._pageNumber} de {total} · Generado el {hoy}')


def tabla(filas, anchos, cabecera=True, estilos_extra=()):
    estilo = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINEA),
    ]
    if cabecera:
        estilo += [('BACKGROUND', (0, 0), (-1, 0), NARANJA_SUAVE), ('LINEBELOW', (0, 0), (-1, 0), 0.8, NARANJA)]
    return Table(filas, colWidths=anchos, style=TableStyle(estilo + list(estilos_extra)), hAlign='LEFT')


def generar_pdf(mascota):
    """Devuelve los bytes del PDF con la historia clínica completa de la mascota."""
    datos = HistorialService.de_la_mascota(mascota)
    consultas = datos['consultas']
    tablero = HistorialService.tablero(mascota, consultas)
    ancho_util = A4[0] - 2 * MARGEN
    bloques = []

    # ---------- Título y ficha del paciente ----------
    bloques += [
        Paragraph(f'Historia clínica de {escape(mascota.nombre)}', ESTILOS['titulo']),
        Spacer(1, 2),
        texto('Consultas, recetas y vacunas registradas por los veterinarios de la clínica, de la más reciente '
              'a la más antigua.', 'bajada'),
        Spacer(1, 10),
    ]
    dueno = mascota.dueno
    ficha = [
        ('Especie y raza', f'{mascota.especie}' + (f' · {mascota.raza}' if mascota.raza else '')),
        ('Sexo', mascota.get_sexo_display() or 'Sin registrar'),
        ('Edad', mascota.edad or 'Sin registrar'),
        ('Peso', f'{mascota.peso_kg} kg' if mascota.peso_kg else 'Sin registrar'),
        ('Dueño', dueno.nombre_completo),
        ('Contacto', f'{dueno.telefono} · {dueno.email}'),
    ]
    celdas = [[[texto(etiqueta.upper(), 'etiqueta'), texto(valor, 'dato')] for etiqueta, valor in ficha[i:i + 3]]
              for i in (0, 3)]
    bloques.append(Table(celdas, colWidths=[ancho_util / 3] * 3, style=TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fbf6f1')),
        ('BOX', (0, 0), (-1, -1), 0.6, LINEA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
    ])))

    # ---------- Resumen en cifras ----------
    cifras = [('Consultas', len(consultas)), ('Recetas', tablero['total_recetas']),
              ('Vacunas aplicadas', len(tablero['carnet'])), ('Vacunas al día', f"{tablero['al_dia']}/{len(tablero['vigentes'])}")]
    bloques += [Spacer(1, 10), Table(
        [[[texto(str(valor), 'cifra'), texto(etiqueta.upper(), 'etiqueta')] for etiqueta, valor in cifras]],
        colWidths=[ancho_util / 4] * 4,
        style=TableStyle([('LINEBEFORE', (1, 0), (-1, -1), 0.6, LINEA), ('LEFTPADDING', (0, 0), (-1, -1), 9),
                          ('VALIGN', (0, 0), (-1, -1), 'TOP')]),
    )]

    # ---------- Carnet de vacunación ----------
    bloques.append(texto('Carnet de vacunación', 'seccion'))
    if tablero['carnet']:
        filas = [[texto(c, 'celda_negrita') for c in ('Vacuna', 'Aplicada', 'Lote', 'Próxima dosis', 'Veterinario', 'Estado')]]
        estilos = []
        for i, linea in enumerate(tablero['carnet'], start=1):
            fondo, color = ESTADOS.get(linea.estado, ESTADOS['reforzada'])
            filas.append([
                texto(linea.vacuna.nombre, 'celda_negrita'), texto(linea.fecha_aplicacion.strftime('%d/%m/%Y'), 'celda'),
                texto(linea.lote or '—', 'celda'),
                texto(linea.proxima_dosis.strftime('%d/%m/%Y') if linea.proxima_dosis else 'Sin refuerzo', 'celda'),
                texto(linea.veterinario.nombre_completo, 'celda'),
                Paragraph(f'<font color="{color.hexval()}"><b>{escape(linea.estado_texto)}</b></font>', ESTILOS['celda']),
            ])
            estilos.append(('BACKGROUND', (5, i), (5, i), fondo))
        bloques.append(tabla(filas, [ancho_util * f for f in (0.27, 0.13, 0.14, 0.15, 0.18, 0.13)],
                             estilos_extra=estilos))
    else:
        bloques.append(texto(f'{mascota.nombre} no tiene vacunas registradas.'))

    # ---------- Consultas ----------
    bloques.append(texto('Consultas', 'seccion'))
    if not consultas:
        bloques.append(texto('Aún no hay consultas registradas.'))
    for consulta in consultas:
        servicio = consulta.cita.servicio if consulta.cita_id else 'Sin cita'
        partes = [
            Table([[texto(f'{fecha(consulta.fecha)} · {fecha(consulta.fecha, "H:i")}', 'consulta'),
                    texto(f'{consulta.veterinario.nombre_completo} · {servicio}'
                          + (f' · {consulta.peso_kg} kg' if consulta.peso_kg else ''), 'derecha')]],
                  colWidths=[ancho_util * 0.45, ancho_util * 0.55],
                  style=TableStyle([('LINEBELOW', (0, 0), (-1, -1), 1.2, NARANJA), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'BOTTOM')])),
            Spacer(1, 5),
        ]
        for etiqueta, valor in (('Motivo', consulta.motivo or 'Sin motivo registrado'), ('Diagnóstico', consulta.diagnostico),
                                ('Indicaciones para el dueño', consulta.indicaciones)):
            if valor:
                partes += [texto(etiqueta.upper(), 'etiqueta'), texto(valor), Spacer(1, 4)]
        recetas = list(consulta.prescripciones.all())
        if recetas:
            filas = [[texto(c, 'celda_negrita') for c in ('Medicamento', 'Dosis', 'Frecuencia', 'Duración', 'Indicaciones')]]
            filas += [[texto(r.medicamento, 'celda_negrita'), texto(r.dosis, 'celda'),
                       texto(f'Cada {r.frecuencia_horas} h', 'celda'),
                       texto(f'{r.duracion_dias} día{"s" if r.duracion_dias != 1 else ""} · {r.tomas} tomas', 'celda'),
                       texto(r.indicaciones or '—', 'celda')] for r in recetas]
            partes += [texto('RECETA', 'etiqueta'), Spacer(1, 2),
                       tabla(filas, [ancho_util * f for f in (0.28, 0.2, 0.14, 0.16, 0.22)])]
        aplicadas = list(consulta.vacunas_aplicadas.all())
        if aplicadas:
            partes += [Spacer(1, 4), texto('VACUNAS APLICADAS EN ESTA CONSULTA', 'etiqueta'),
                       texto(', '.join(a.vacuna.nombre for a in aplicadas))]
        bloques += [KeepTogether(partes[:4]), *partes[4:], Spacer(1, 12)]

    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=ALTO_CABECERA + 10 * mm, bottomMargin=ALTO_PIE + 8 * mm,
        title=f'Historia clínica de {mascota.nombre}', author='Woof · Sistema veterinario',
    )
    documento.build(bloques, canvasmaker=lambda *a, **k: PaginaNumerada(*a, mascota=mascota.nombre, **k))
    return salida.getvalue()


def nombre_del_archivo(mascota):
    return f'historia-clinica-{mascota.nombre.lower().replace(" ", "-")}-{timezone.localdate():%Y%m%d}.pdf'
