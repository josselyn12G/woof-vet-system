"""
Datos de los gráficos de los paneles, armados en el servidor (sin librerías de JavaScript): la plantilla
solo dibuja. Colores en tonos de naranja y el marrón de la marca, sin degradados.

- dona(partes): un anillo repartido (citas por estado, cuentas por rol...). El círculo tiene radio 15.915,
  así su perímetro mide 100 y cada parte se dibuja con stroke-dasharray = su porcentaje.
- columnas(partes): barras verticales con su alto relativo a la más alta.
- grafico_de_linea(fechas, valores): la línea de citas por día (paneles e indicadores).
- grafico_de_peso(barras): la línea del peso de la mascota en su historia clínica.

Están en compartido porque los usan panel, citas e historial: son presentación, no reglas del negocio, y así
ninguna app tiene que importar de panel (que está arriba de todas).
"""

# Del más fuerte al más suave; el marrón y el gris cierran para los últimos
COLORES = ['#ee9a35', '#c26a12', '#f7c27a', '#7a3c0a', '#fbd9a8', '#3b2a22', '#d6d6db']


def dona(partes):
    """partes: [(etiqueta, valor)] → {total, segmentos: [{etiqueta, valor, porcentaje, color, largo, desde}]}."""
    total = sum(valor for _, valor in partes)
    segmentos = []
    acumulado = 0
    for i, (etiqueta, valor) in enumerate(partes):
        porcentaje = valor * 100 / total if total else 0
        segmentos.append({
            'etiqueta': etiqueta, 'valor': valor, 'porcentaje': round(porcentaje),
            'color': COLORES[i % len(COLORES)],
            # El trazo empieza arriba (offset 25) y cada parte arranca donde terminó la anterior
            'largo': round(porcentaje, 2), 'desde': round(25 - acumulado, 2),
        })
        acumulado += porcentaje
    return {'total': total, 'segmentos': segmentos}


def columnas(partes):
    """partes: [(etiqueta, valor)] → [{etiqueta, valor, alto (0-100), color}], el más alto llega a 100."""
    mayor = max((valor for _, valor in partes), default=0)
    return [
        {'etiqueta': etiqueta, 'valor': valor, 'alto': round(valor * 100 / mayor) if mayor else 0,
         'color': COLORES[0] if i == 0 else COLORES[2] if valor else COLORES[6]}
        for i, (etiqueta, valor) in enumerate(sorted(partes, key=lambda parte: -parte[1]))
    ]


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


def grafico_de_peso(barras, ancho=600, alto=180, margen=14):
    """
    Los puntos del gráfico de peso (SVG): x repartido a lo ancho y y entre el peso más bajo y el más alto.
    Con un solo registro, la línea queda plana de un borde al otro y el punto al final.
    Devuelve los puntos, la línea y el área de abajo (la plantilla los pinta con localize off: sin comas decimales).
    """
    if not barras:
        return None
    if len(barras) == 1:
        y = alto / 2
        punto = {'x': ancho - margen, 'y': y, 'peso': barras[0]['peso'], 'fecha': barras[0]['fecha']}
        return {
            'puntos': [punto], 'linea': f'{margen},{y} {ancho - margen},{y}',
            'area': f'M{margen},{alto} L{margen},{y} L{ancho - margen},{y} L{ancho - margen},{alto} Z',
            'ancho': ancho, 'alto': alto, 'ultimo': punto,
        }
    pesos = [float(barra['peso']) for barra in barras]
    minimo, maximo = min(pesos), max(pesos)
    rango = (maximo - minimo) or 1
    puntos = []
    for i, barra in enumerate(barras):
        x = ancho / 2 if len(barras) == 1 else margen + i * (ancho - 2 * margen) / (len(barras) - 1)
        y = alto / 2 if maximo == minimo else margen + (maximo - float(barra['peso'])) * (alto - 2 * margen) / rango
        puntos.append({'x': round(x, 1), 'y': round(y, 1), 'peso': barra['peso'], 'fecha': barra['fecha']})
    linea = ' '.join(f"{p['x']},{p['y']}" for p in puntos)
    area = f"M{puntos[0]['x']},{alto} L" + ' L'.join(f"{p['x']},{p['y']}" for p in puntos) + f" L{puntos[-1]['x']},{alto} Z"
    return {'puntos': puntos, 'linea': linea, 'area': area, 'ancho': ancho, 'alto': alto, 'ultimo': puntos[-1]}
