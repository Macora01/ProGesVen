from flask import Flask, render_template, request, jsonify, session
import csv
import os
from datetime import datetime, timedelta
import json

# Importar configuración
from config import get_config, ensure_directories, validate_sales_code, validate_factory_code

app = Flask(__name__)

# Cargar configuración
app_config = get_config()
app.config.from_object(app_config)

# Configuración de directorios desde config
DATA_DIR = app_config.DATA_DIR
SALES_DIR = app_config.SALES_DIR
COMMENTS_DIR = app_config.COMMENTS_DIR
PHOTOS_DIR = app_config.PHOTOS_DIR
TUTORIALS_DIR = app_config.TUTORIALS_DIR

# Asegurar que los directorios existan
ensure_directories(app_config)

def load_csv(filename, fieldnames=None):
    """Cargar archivo CSV con manejo de errores"""
    filepath = os.path.join(DATA_DIR, filename)
    data = []
    try:
        with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
            # Detectar delimitador
            sample = file.read(1024)
            file.seek(0)
            
            # Determinar delimitador
            if ';' in sample:
                delimiter = ';'
            elif ',' in sample:
                delimiter = ','
            else:
                delimiter = ','  # por defecto
            
            print(f"Archivo: {filename}, Delimitador detectado: '{delimiter}'")  # Debug
            
            # Manejar archivos sin encabezados
            if filename == 'productos.csv' and fieldnames:
                reader = csv.DictReader(file, delimiter=delimiter, fieldnames=fieldnames)
            else:
                reader = csv.DictReader(file, delimiter=delimiter)
                
            for row in reader:
                # Limpiar valores y normalizar nombres de columnas
                cleaned_row = {}
                for k, v in row.items():
                    if v is not None:
                        # Normalizar nombres de columnas (minúsculas, sin espacios)
                        clean_key = k.strip().lower().replace(' ', '_')
                        cleaned_row[clean_key] = v.strip() if isinstance(v, str) else str(v)
                    else:
                        cleaned_row[k.strip().lower()] = ''
                
                data.append(cleaned_row)
                
        print(f"Archivo {filename} cargado: {len(data)} registros")  # Debug
        if data:
            print(f"Columnas disponibles: {list(data[0].keys())}")  # Debug
            
    except Exception as e:
        print(f"Error cargando {filename}: {e}")
    return data

def save_csv(filename, data, fieldnames):
    """Guardar datos en CSV"""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'w', newline='', encoding=app_config.CSV_ENCODING) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
            writer.writeheader()
            writer.writerows(data)
        return True
    except Exception as e:
        print(f"Error guardando {filename}: {e}")
        return False

# Rutas principales
@app.route('/')
def index():
    # Calcular notificaciones de solicitudes pendientes
    pendientes_count = 0
    try:
        solicitudes = load_csv('solicitudes.csv')
        # Contar solo las que tienen estado "Pendiente"
        pendientes_count = len([s for s in solicitudes if s.get('estado') == 'Pendiente'])
    except:
        pass # Si no hay archivo, el contador queda en 0
        
    return render_template('index.html', pendientes_count=pendientes_count)

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/api/search_product', methods=['POST'])
def api_search_product():
    code = request.json.get('code', '').strip().upper()
    
    # Si el código tiene 5 caracteres y no empieza con BI, intentar agregar BI6
    if len(code) == 5 and not code.startswith('BI'):
        potential_code = 'BI6' + code
        # Primero buscar con el código completo
        productos = load_csv('productos.csv')
        product = None
        for p in productos:
            if p.get('cod_venta', '') == potential_code:
                product = p
                code = potential_code  # Actualizar el código para usar el completo
                break
        
        if product:
            # Verificar existencia de imagen
            cod_fabrica = product.get('cod_fabrica', '')
            image_path = None
            for ext in ['.jpg', '.jpeg', '.png']:
                potential_path = os.path.join(PHOTOS_DIR, f"{cod_fabrica}{ext}")
                if os.path.exists(potential_path):
                    image_path = f"/static/fotos/{cod_fabrica}{ext}"
                    break
            
            return jsonify({
                'success': True,
                'product': product,
                'image': image_path
            })
    
    # Validar formato del código (código original o el completo después de la transformación)
    if not (validate_factory_code(code, app_config) or validate_sales_code(code, app_config)):
        return jsonify({
            'success': False,
            'message': 'Formato de código inválido. Use código fábrica (3-8 caracteres) o los últimos 5 dígitos del código venta'
        })
    
    productos = load_csv('productos.csv')
    
    # Buscar producto
    product = None
    for p in productos:
        if p.get('cod_fabrica', '') == code or p.get('cod_venta', '') == code:
            product = p
            break
    
    if product:
        # Verificar existencia de imagen
        cod_fabrica = product.get('cod_fabrica', '')
        image_path = None
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_path = os.path.join(PHOTOS_DIR, f"{cod_fabrica}{ext}")
            if os.path.exists(potential_path):
                image_path = f"/static/fotos/{cod_fabrica}{ext}"
                break
        
        return jsonify({
            'success': True,
            'product': product,
            'image': image_path
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Producto no encontrado'
        })

@app.route('/sales')
def sales():
    telefonos = load_csv('telefonos.csv')
    print(f"Teléfonos cargados: {telefonos}")  # Debug
    
    # Extraer lugares únicos - manejar diferentes nombres de columna
    lugares_set = set()
    for t in telefonos:
        # Intentar diferentes posibles nombres de columna
        lugar = t.get('lugar') or t.get('Lugar') or t.get('nombrepunto') or t.get('Nombre')
        if lugar and isinstance(lugar, str):
            lugar = lugar.strip()
            if lugar:
                lugares_set.add(lugar)
    
    lugares = sorted(list(lugares_set))
    print(f"Lugares encontrados: {lugares}")  # Debug
    
    return render_template('sales.html', lugares=lugares)
@app.route('/api/record_sale', methods=['POST'])
def api_record_sale():
    lugar = request.json.get('lugar')
    codigo = request.json.get('codigo', '').strip().upper()
    
    # Validar producto - usando fieldnames específicos para productos
    productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
    
    product = None
    for p in productos:
        if p.get('cod_fabrica') == codigo or p.get('cod_venta') == codigo:
            product = p
            break
    
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'})
    
    # Guardar venta
    fecha = datetime.now().strftime('%Y-%m-%d')
    
    # Limpiar nombre del lugar para el archivo
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{lugar_limpio}_{fecha}.csv"
    filepath = os.path.join(SALES_DIR, filename)
    
    fieldnames = ['timestamp', 'lugar', 'cod_fabrica', 'cod_venta', 'descripcion', 'precio']
    
    # Si el archivo no existe, crearlo con header
    file_exists = os.path.exists(filepath)
    
    try:
        with open(filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'lugar': lugar,
                'cod_fabrica': product.get('cod_fabrica', ''),
                'cod_venta': product.get('cod_venta', ''),
                'descripcion': product.get('descripcion', ''),
                'precio': product.get('precio', '')
            })
        
        return jsonify({'success': True, 'message': 'Venta registrada correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'})


@app.route('/events')
def events():
    # Usar bazares.csv para eventos (con fechas)
    bazares = load_csv('bazares.csv')
    
    # Filtrar bazares activos (fecha término >= fecha actual)
    from datetime import datetime
    hoy = datetime.now().date()
    
    bazares_activos = []
    for bazar in bazares:
        try:
            # Convertir fecha término de formato dd-mm-yy a objeto date
            fecha_termino_str = bazar.get('fech_termino', '')
            if fecha_termino_str:
                fecha_termino = datetime.strptime(fecha_termino_str, '%d-%m-%y').date()
                # Solo incluir si la fecha de término es mayor o igual a hoy
                if fecha_termino >= hoy:
                    bazares_activos.append(bazar)
        except (ValueError, TypeError) as e:
            print(f"Error procesando fecha para bazar {bazar.get('nombrepunto', '')}: {e}")
            # En caso de error, incluir el bazar por seguridad
            bazares_activos.append(bazar)
    
    print(f"Bazares activos encontrados: {len(bazares_activos)} de {len(bazares)} totales")
    
    return render_template('events.html', bazares=bazares_activos)

@app.route('/api/save_comment_events', methods=['POST'])
def api_save_comment_events():
    comment = request.json.get('comment', '').strip()
    if comment:
        fecha = datetime.now().strftime('%Y-%m-%d')
        filename = f"commentsventa_{fecha}.csv"
        filepath = os.path.join(COMMENTS_DIR, filename)
        
        fieldnames = ['timestamp', 'comment']
        file_exists = os.path.exists(filepath)
        
        try:
            with open(filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'comment': comment
                })
            
            return jsonify({'success': True, 'message': 'Comentario guardado'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'})
    
    return jsonify({'success': False, 'message': 'Comentario vacío'})

@app.route('/points')
def points():
    # Usar puntosventa.csv para puntos de venta (sin fechas)
    puntos = load_csv('puntosventa.csv')
    return render_template('points.html', puntos=puntos)

@app.route('/api/save_comment_points', methods=['POST'])
def api_save_comment_points():
    comment = request.json.get('comment', '').strip()
    if comment:
        fecha = datetime.now().strftime('%Y-%m-%d')
        filename = f"commentsbazar_{fecha}.csv"
        filepath = os.path.join(COMMENTS_DIR, filename)
        
        fieldnames = ['timestamp', 'comment']
        file_exists = os.path.exists(filepath)
        
        try:
            with open(filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'comment': comment
                })
            
            return jsonify({'success': True, 'message': 'Comentario guardado'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'})
    
    return jsonify({'success': False, 'message': 'Comentario vacío'})

@app.route('/tutorials')
def tutorials():
    tutoriales = load_csv('tutoriales.csv')
    return render_template('tutorials.html', tutoriales=tutoriales)

@app.route('/info')
def info():
    # Verificar acceso
    if not session.get('authorized'):
        return render_template('auth_required.html')
    
    telefonos = load_csv('telefonos.csv')
    return render_template('info.html', telefonos=telefonos)

# Nueva ruta para el dashboard
@app.route('/dashboard')
def dashboard():
    # Verificar acceso
    if not session.get('authorized'):
        return render_template('auth_required.html')
    
    return render_template('dashboard.html')

# API para datos del dashboard
# @app.route('/api/dashboard_data')
# def api_dashboard_data():
#    if not session.get('authorized'):
#        return jsonify({'error': 'No autorizado'}), 403
    
#    data = {
#        'sales_summary': get_sales_summary(),
#        'top_products': get_top_products(),
#        'sales_by_location': get_sales_by_location(),
#        'recent_activity': get_recent_activity(),
#        'performance_metrics': get_performance_metrics()
#    }
#    return jsonify(data)

# Funciones auxiliares para estadísticas
def get_sales_summary():
    """Resumen general de ventas del día"""
    today = datetime.now().strftime('%Y-%m-%d')
    total_sales = 0
    total_amount = 0
    locations_active = set()
    
    # Buscar archivos de ventas de hoy
    for filename in os.listdir(SALES_DIR):
        if today in filename:
            filepath = os.path.join(SALES_DIR, filename)
            location = filename.replace(f'_{today}.csv', '')
            locations_active.add(location)
            
            try:
                with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                    reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                    for row in reader:
                        total_sales += 1
                        # Limpiar y convertir precio
                        precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                        if precio.isdigit():
                            total_amount += int(precio)
            except Exception as e:
                print(f"Error procesando {filename}: {e}")
    
    return {
        'total_sales': total_sales,
        'total_amount': total_amount,
        'active_locations': len(locations_active),
        'date': today
    }

def get_top_products(limit=5):
    """Productos más vendidos del día"""
    today = datetime.now().strftime('%Y-%m-%d')
    product_sales = {}
    
    for filename in os.listdir(SALES_DIR):
        if today in filename:
            filepath = os.path.join(SALES_DIR, filename)
            try:
                with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                    reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                    for row in reader:
                        product_code = row.get('cod_venta') or row.get('cod_fabrica', '')
                        if product_code:
                            if product_code in product_sales:
                                product_sales[product_code]['count'] += 1
                            else:
                                # Buscar información del producto
                                productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
                                product_info = next((p for p in productos if p.get('cod_fabrica') == product_code or p.get('cod_venta') == product_code), {})
                                product_sales[product_code] = {
                                    'count': 1,
                                    'description': product_info.get('descripcion', 'Producto no encontrado'),
                                    'price': product_info.get('precio', 0)
                                }
            except Exception as e:
                print(f"Error procesando {filename}: {e}")
    
    # Ordenar por cantidad vendida
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['count'], reverse=True)
    return sorted_products[:limit]

def get_sales_by_location():
    """Ventas por ubicación del día"""
    today = datetime.now().strftime('%Y-%m-%d')
    location_sales = {}
    
    for filename in os.listdir(SALES_DIR):
        if today in filename:
            filepath = os.path.join(SALES_DIR, filename)
            location = filename.replace(f'_{today}.csv', '')
            total_amount = 0
            total_sales = 0
            
            try:
                with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                    reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                    for row in reader:
                        total_sales += 1
                        precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                        if precio.isdigit():
                            total_amount += int(precio)
            except Exception as e:
                print(f"Error procesando {filename}: {e}")
            
            location_sales[location] = {
                'total_sales': total_sales,
                'total_amount': total_amount
            }
    
    return location_sales

def get_recent_activity():
    """Actividad reciente (últimas 5 ventas)"""
    today = datetime.now().strftime('%Y-%m-%d')
    recent_sales = []
    
    for filename in os.listdir(SALES_DIR):
        if today in filename:
            filepath = os.path.join(SALES_DIR, filename)
            location = filename.replace(f'_{today}.csv', '')
            
            try:
                with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                    reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                    rows = list(reader)
                    # Tomar las últimas 5 ventas de este archivo
                    for row in rows[-5:]:
                        recent_sales.append({
                            'location': location,
                            'product': row.get('cod_venta') or row.get('cod_fabrica', ''),
                            'description': row.get('descripcion', ''),
                            'price': row.get('precio', '0'),
                            'timestamp': row.get('timestamp', '')
                        })
            except Exception as e:
                print(f"Error procesando {filename}: {e}")
    
    # Ordenar por timestamp y tomar las 5 más recientes
    recent_sales.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return recent_sales[:5]

def get_performance_metrics():
    """Métricas de rendimiento"""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    # Esta es una implementación básica - se puede expandir
    return {
        'avg_daily_sales': 150000,  # Ejemplo - implementar cálculo real
        'best_selling_category': 'Jeans',
        'peak_hour': '16:00-17:00',
        'conversion_rate': '68%'
    }


@app.route('/api/authorize', methods=['POST'])
def api_authorize():
    password = request.json.get('password', '')
    # Usar contraseña de la configuración
    if password == app_config.INFO_PASSWORD:
        session['authorized'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Contraseña incorrecta'})

@app.route('/under_construction')
def under_construction():
    return render_template('under_construction.html')

# =============================================================================
# NUEVAS FUNCIONES PARA REPORTES AVANZADOS
# =============================================================================
def get_period_data(period):
    """Obtener datos para períodos predefinidos - Versión corregida"""
    today = datetime.now().date()
    
    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = today.replace(day=1)
        # Último día del mes
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today
        end_date = today
    
    # Usar la misma función que para rangos personalizados
    return get_sales_data_by_date_range(start_date, end_date)




def get_sales_data_by_date_range(start_date, end_date):
    """Obtener datos de ventas y devoluciones para un rango de fechas específico - Versión mejorada"""
    total_sales = 0
    total_returns = 0
    total_amount = 0
    locations_active = set()
    daily_data = {}
    product_sales = {}
    location_sales = {}
    
    # Convertir fechas a objetos datetime si son strings
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Cargar productos para obtener descripciones
    productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        daily_sales = 0
        daily_returns = 0
        daily_amount = 0
        daily_locations = set()
        
        # Procesar archivos de ventas de esta fecha
        for filename in os.listdir(SALES_DIR):
            if date_str in filename and not filename.startswith('devoluciones_'):
                filepath = os.path.join(SALES_DIR, filename)
                location = filename.replace(f'_{date_str}.csv', '')
                daily_locations.add(location)
                locations_active.add(location)
                
                try:
                    with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                        reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                        for row in reader:
                            total_sales += 1
                            daily_sales += 1
                            
                            # Procesar producto
                            product_code = row.get('cod_venta') or row.get('cod_fabrica', '')
                            if product_code:
                                if product_code not in product_sales:
                                    # Buscar descripción del producto
                                    descripcion = next((p.get('descripcion', '') for p in productos 
                                                      if p.get('cod_venta') == product_code or p.get('cod_fabrica') == product_code), product_code)
                                    product_sales[product_code] = {
                                        'description': descripcion,
                                        'sales_count': 0,
                                        'returns_count': 0,
                                        'amount': 0
                                    }
                                product_sales[product_code]['sales_count'] += 1
                            
                            # Procesar ubicación
                            if location not in location_sales:
                                location_sales[location] = {
                                    'sales_count': 0,
                                    'returns_count': 0,
                                    'amount': 0
                                }
                            location_sales[location]['sales_count'] += 1
                            
                            # Procesar monto
                            precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                            if precio.isdigit():
                                amount = int(precio)
                                total_amount += amount
                                daily_amount += amount
                                if product_code:
                                    product_sales[product_code]['amount'] += amount
                                location_sales[location]['amount'] += amount
                except Exception as e:
                    print(f"Error procesando {filename}: {e}")
        
        # Procesar archivos de devoluciones de esta fecha
        returns_filename = f"devoluciones_{date_str}.csv"
        returns_filepath = os.path.join(SALES_DIR, returns_filename)
        if os.path.exists(returns_filepath):
            try:
                with open(returns_filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                    reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                    for row in reader:
                        total_returns += 1
                        daily_returns += 1
                        
                        # Procesar producto en devolución
                        product_code = row.get('cod_venta') or row.get('cod_fabrica', '')
                        location = row.get('lugar', '')
                        
                        if product_code:
                            if product_code not in product_sales:
                                descripcion = next((p.get('descripcion', '') for p in productos 
                                                  if p.get('cod_venta') == product_code or p.get('cod_fabrica') == product_code), product_code)
                                product_sales[product_code] = {
                                    'description': descripcion,
                                    'sales_count': 0,
                                    'returns_count': 0,
                                    'amount': 0
                                }
                            product_sales[product_code]['returns_count'] += 1
                        
                        # Procesar ubicación en devolución
                        if location and location not in location_sales:
                            location_sales[location] = {
                                'sales_count': 0,
                                'returns_count': 0,
                                'amount': 0
                            }
                        if location:
                            location_sales[location]['returns_count'] += 1
                        
                        # Procesar monto de devolución
                        precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                        if precio.lstrip('-').isdigit():
                            amount = int(precio)
                            total_amount += amount
                            daily_amount += amount
                            if product_code:
                                product_sales[product_code]['amount'] += amount
                            if location:
                                location_sales[location]['amount'] += amount
            except Exception as e:
                print(f"Error procesando {returns_filename}: {e}")
        
        daily_data[date_str] = {
            'sales': daily_sales,
            'returns': daily_returns,
            'amount': daily_amount,
            'locations': len(daily_locations)
        }
        
        current_date += timedelta(days=1)
    
    net_sales = total_sales - total_returns
    
    # Preparar datos para top productos (ordenar por monto)
    top_products_all = []
    for code, info in product_sales.items():
        net_count = info['sales_count'] - info['returns_count']
        if net_count > 0 or info['amount'] != 0:  # Solo incluir productos con actividad
            top_products_all.append([code, {
                'description': info['description'],
                'count': net_count,
                'amount': info['amount']
            }])
    
    # Ordenar por monto (descendente)
    top_products_all.sort(key=lambda x: x[1]['amount'], reverse=True)
    top_5_products = top_products_all[:5]
    top_10_products = top_products_all[:10]
    
    # Preparar datos para gráfico de top productos
    top_products_chart = {
        'names': [p[1]['description'][:20] + '...' if len(p[1]['description']) > 20 else p[1]['description'] for p in top_5_products],
        'amounts': [p[1]['amount'] for p in top_5_products]
    }
    
    # Preparar datos para ubicaciones
    location_sales_clean = {}
    for location, info in location_sales.items():
        net_count = info['sales_count'] - info['returns_count']
        if net_count > 0 or info['amount'] != 0:  # Solo incluir ubicaciones con actividad
            location_sales_clean[location] = {
                'count': net_count,
                'amount': info['amount']
            }
    
    return {
        'total_sales': total_sales,
        'total_returns': total_returns,
        'net_sales': net_sales,
        'total_amount': total_amount,
        'active_locations': len(locations_active),
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'daily_data': daily_data,
        'top_products': top_10_products,  # Para la tabla de top 10
        'location_sales': location_sales_clean,
        'chart_data': {
            'daily_evolution': {
                'dates': list(daily_data.keys()),
                'sales': [daily_data[date]['sales'] for date in sorted(daily_data.keys())],
                'returns': [daily_data[date]['returns'] for date in sorted(daily_data.keys())],
                'amounts': [daily_data[date]['amount'] for date in sorted(daily_data.keys())]
            },
            'top_products': top_products_chart,
            'top_locations': {'names': [], 'amounts': []}  # Se puede implementar si es necesario
        }
    }

# =============================================================================
# NUEVAS RUTAS PARA REPORTES AVANZADOS
# =============================================================================

@app.route('/api/reports')
def api_reports():
    if not session.get('authorized'):
        return jsonify({'error': 'No autorizado'}), 403
    
    period = request.args.get('period', 'today')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    print(f"Solicitud de reporte - Periodo: {period}, Start: {start_date}, End: {end_date}")  # Debug
    
    if start_date and end_date and period == 'custom':
        # Usar rango personalizado
        data = get_sales_data_by_date_range(start_date, end_date)
    else:
        # Usar período predefinido
        data = get_period_data(period)
    
    print(f"Datos devueltos - Ventas: {data.get('total_sales')}, Devoluciones: {data.get('total_returns')}")  # Debug
    print(f"Top productos: {len(data.get('top_products', []))}")  # Debug
    print(f"Ubicaciones: {len(data.get('location_sales', {}))}")  # Debug
    
    return jsonify(data)

# Mantener la ruta original del dashboard para compatibilidad
@app.route('/api/dashboard_data')
def api_dashboard_data():
    if not session.get('authorized'):
        return jsonify({'error': 'No autorizado'}), 403
    
    # Por defecto mostrar datos del día actual
    data = get_period_data('today')
    return jsonify(data)

def get_all_daily_sales(lugar):
    """Obtener todas las ventas del día para un lugar específico"""
    today = datetime.now().strftime('%Y-%m-%d')
    sales_data = []
    total_amount = 0
    total_sales = 0
    
    # Limpiar nombre del lugar para el archivo
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{lugar_limpio}_{today}.csv"
    filepath = os.path.join(SALES_DIR, filename)
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                for row in reader:
                    sales_data.append({
                        'cod_fabrica': row.get('cod_fabrica', ''),
                        'cod_venta': row.get('cod_venta', ''),
                        'descripcion': row.get('descripcion', ''),
                        'precio': row.get('precio', '0'),
                        'timestamp': row.get('timestamp', '')
                    })
                    total_sales += 1
                    precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                    if precio.isdigit():
                        total_amount += int(precio)
        except Exception as e:
            print(f"Error leyendo archivo diario {filename}: {e}")
    
        return {
        'sales_data': sales_data,
        'total_amount': total_amount,
        'total_sales': total_sales,
        'lugar': lugar,
        'date': today
    }
    
@app.route('/api/get_all_daily_sales/<lugar>')
def api_get_all_daily_sales(lugar):
    """API para obtener todas las ventas del día de un lugar específico"""
    try:
        daily_data = get_all_daily_sales(lugar)
        return jsonify({
            'success': True,
            'daily_data': daily_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error obteniendo ventas del día: {str(e)}'
        })
# =============================================================================
# FUNCIONALIDAD DE DEVOLUCIONES
# =============================================================================

@app.route('/api/process_return', methods=['POST'])
def api_process_return():
    """Procesar devolución de producto"""
    lugar = request.json.get('lugar')
    codigo = request.json.get('codigo', '').strip().upper()
    motivo = request.json.get('motivo', '').strip()
    
    # Validar producto
    productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
    
    product = None
    for p in productos:
        if p.get('cod_fabrica') == codigo or p.get('cod_venta') == codigo:
            product = p
            break
    
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'})
    
    # Verificar que exista al menos una venta de este producto hoy
    today = datetime.now().strftime('%Y-%m-%d')
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{lugar_limpio}_{today}.csv"
    filepath = os.path.join(SALES_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'No hay ventas registradas hoy para este lugar'})
    
    # Contar ventas de este producto hoy
    product_sales_count = 0
    try:
        with open(filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
            reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
            for row in reader:
                row_codigo = row.get('cod_venta') or row.get('cod_fabrica', '')
                if row_codigo == codigo:
                    product_sales_count += 1
    except Exception as e:
        print(f"Error leyendo ventas del día: {e}")
    
    if product_sales_count == 0:
        return jsonify({'success': False, 'message': 'No se encontraron ventas de este producto hoy'})
    
    # Guardar devolución (con precio negativo)
    returns_filename = f"devoluciones_{today}.csv"
    returns_filepath = os.path.join(SALES_DIR, returns_filename)
    
    fieldnames = ['timestamp', 'lugar', 'cod_fabrica', 'cod_venta', 'descripcion', 'precio', 'motivo', 'tipo']
    file_exists = os.path.exists(returns_filepath)
    
    try:
        with open(returns_filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
            if not file_exists:
                writer.writeheader()
            
            # Obtener precio original y hacerlo negativo
            precio_original = product.get('precio', '0')
            try:
                # Convertir a número, hacer negativo y volver a string
                precio_num = float(str(precio_original).replace('$', '').replace('.', '').strip())
                precio_devolucion = f"-{precio_num}"
            except:
                precio_devolucion = f"-{precio_original}"
            
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'lugar': lugar,
                'cod_fabrica': product.get('cod_fabrica', ''),
                'cod_venta': product.get('cod_venta', ''),
                'descripcion': product.get('descripcion', ''),
                'precio': precio_devolucion,
                'motivo': motivo,
                'tipo': 'devolucion'
            })
        
        return jsonify({
            'success': True, 
            'message': f'Devolución registrada correctamente. Ventas encontradas del producto: {product_sales_count}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al guardar devolución: {str(e)}'})

def get_all_daily_transactions(lugar):
    """Obtener todas las transacciones del día (ventas y devoluciones)"""
    today = datetime.now().strftime('%Y-%m-%d')
    transactions = []
    total_amount = 0
    total_sales = 0
    total_returns = 0
    returns_amount = 0
    
    # Cargar ventas del día
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    sales_filename = f"{lugar_limpio}_{today}.csv"
    sales_filepath = os.path.join(SALES_DIR, sales_filename)
    
    if os.path.exists(sales_filepath):
        try:
            with open(sales_filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                for row in reader:
                    row['tipo'] = 'venta'
                    transactions.append(row)
                    total_sales += 1
                    
                    precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                    if precio and precio != '' and precio.lstrip('-').isdigit():
                        total_amount += int(precio)
        except Exception as e:
            print(f"Error leyendo ventas del día {sales_filename}: {e}")
    
    # Cargar devoluciones del día
    returns_filename = f"devoluciones_{today}.csv"
    returns_filepath = os.path.join(SALES_DIR, returns_filename)
    
    if os.path.exists(returns_filepath):
        try:
            with open(returns_filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                for row in reader:
                    # Solo incluir devoluciones de este lugar
                    if row.get('lugar') == lugar:
                        row['tipo'] = 'devolucion'
                        transactions.append(row)
                        total_returns += 1
                        
                        precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                        if precio and precio != '' and precio.lstrip('-').isdigit():
                            total_amount += int(precio)  # Suma el valor negativo
                            returns_amount += abs(int(precio))
        except Exception as e:
            print(f"Error leyendo devoluciones {returns_filename}: {e}")
    
    # Ordenar transacciones por timestamp
    transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return {
        'transactions': transactions,
        'total_amount': total_amount,
        'total_sales': total_sales,
        'total_returns': total_returns,
        'returns_amount': returns_amount,
        'net_sales': total_sales - total_returns,
        'lugar': lugar,
        'date': today
    }

@app.route('/api/get_daily_transactions/<lugar>')
def api_get_daily_transactions(lugar):
    """API para obtener todas las transacciones del día (ventas + devoluciones)"""
    try:
        daily_data = get_all_daily_transactions(lugar)
        return jsonify({
            'success': True,
            'daily_data': daily_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error obteniendo transacciones del día: {str(e)}'
        })
# =============================================================================
# FUNCIONALIDAD DE DEVOLUCIONES - CORREGIDO
# =============================================================================

@app.route('/api/process_product_return', methods=['POST'])
def api_process_product_return():
    """Procesar devolución de producto"""
    lugar = request.json.get('lugar')
    codigo = request.json.get('codigo', '').strip().upper()
    motivo = request.json.get('motivo', '').strip()
    
    # Validar producto
    productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
    
    product = None
    for p in productos:
        if p.get('cod_fabrica') == codigo or p.get('cod_venta') == codigo:
            product = p
            break
    
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'})
    
    # Guardar devolución (con precio negativo)
    fecha = datetime.now().strftime('%Y-%m-%d')
    
    # Limpiar nombre del lugar para el archivo
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"devoluciones_{fecha}.csv"
    filepath = os.path.join(SALES_DIR, filename)
    
    fieldnames = ['timestamp', 'lugar', 'cod_fabrica', 'cod_venta', 'descripcion', 'precio', 'motivo', 'tipo']
    
    # Si el archivo no existe, crearlo con header
    file_exists = os.path.exists(filepath)
    
    try:
        with open(filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
            if not file_exists:
                writer.writeheader()
            
            # Convertir precio a negativo
            precio_original = product.get('precio', '0')
            try:
                # Intentar convertir a número y hacer negativo
                precio_num = int(precio_original.replace('$', '').replace('.', '').strip())
                precio_devolucion = -precio_num
            except:
                precio_devolucion = f"-{precio_original}"
            
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'lugar': lugar,
                'cod_fabrica': product.get('cod_fabrica', ''),
                'cod_venta': product.get('cod_venta', ''),
                'descripcion': product.get('descripcion', ''),
                'precio': precio_devolucion,
                'motivo': motivo,
                'tipo': 'devolucion'
            })
        
        return jsonify({'success': True, 'message': 'Devolución registrada correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'})

def get_daily_transactions_with_returns(lugar):
    """Obtener todas las transacciones del día (ventas y devoluciones) para un lugar específico"""
    today = datetime.now().strftime('%Y-%m-%d')
    transactions = []
    total_amount = 0
    total_sales = 0
    total_returns = 0
    returns_amount = 0
    
    # Cargar ventas del día
    lugar_limpio = "".join(c for c in lugar if c.isalnum() or c in (' ', '-', '_')).rstrip()
    sales_filename = f"{lugar_limpio}_{today}.csv"
    sales_filepath = os.path.join(SALES_DIR, sales_filename)
    
    if os.path.exists(sales_filepath):
        try:
            with open(sales_filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                for row in reader:
                    row['tipo'] = 'venta'
                    transactions.append(row)
                    total_sales += 1
                    
                    precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                    if precio and precio != '' and precio.lstrip('-').isdigit():
                        total_amount += int(precio)
        except Exception as e:
            print(f"Error leyendo ventas del día {sales_filename}: {e}")
    
    # Cargar devoluciones del día (de todos los lugares, pero filtraremos por lugar)
    returns_filename = f"devoluciones_{today}.csv"
    returns_filepath = os.path.join(SALES_DIR, returns_filename)
    
    if os.path.exists(returns_filepath):
        try:
            with open(returns_filepath, 'r', encoding=app_config.CSV_ENCODING) as file:
                reader = csv.DictReader(file, delimiter=app_config.CSV_DELIMITER)
                for row in reader:
                    # Solo incluir devoluciones de este lugar
                    if row.get('lugar') == lugar:
                        row['tipo'] = 'devolucion'
                        transactions.append(row)
                        total_returns += 1
                        
                        precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                        if precio and precio != '' and precio.lstrip('-').isdigit():
                            total_amount += int(precio)  # Suma el valor negativo
                            returns_amount += abs(int(precio))
        except Exception as e:
            print(f"Error leyendo devoluciones {returns_filename}: {e}")
    
    # Ordenar transacciones por timestamp
    transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return {
        'transactions': transactions,
        'total_amount': total_amount,
        'total_sales': total_sales,
        'total_returns': total_returns,
        'returns_amount': returns_amount,
        'net_sales': total_sales - total_returns,
        'lugar': lugar,
        'date': today
    }

@app.route('/api/get_daily_transactions_with_returns/<lugar>')
def api_get_daily_transactions_with_returns(lugar):
    """API para obtener todas las transacciones del día (ventas + devoluciones) de un lugar específico"""
    try:
        daily_data = get_daily_transactions_with_returns(lugar)
        return jsonify({
            'success': True,
            'daily_data': daily_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error obteniendo transacciones del día: {str(e)}'
        })

# =============================================================================
# SISTEMA DE SOLICITUDES - COPIAR Y PEGAR JUNTO
# =============================================================================

# =============================================================================
# BLOQUE COMPLETO SOLICITUDES - REEMPLAZAR TODO
# =============================================================================

@app.route('/solicitudes')
def solicitudes():
    return render_template('solicitudes.html')

@app.route('/api/solicitudes_login', methods=['POST'])
def api_solicitudes_login():
    try:
        input_user = request.json.get('identificador', '').strip().lower()
        telefonos = load_csv('telefonos.csv')
        
        usuario = next((t for t in telefonos if str(t.get('nombre', '')).strip().lower() == input_user), None)
        
        if usuario:
            es_admin = str(usuario.get('allow', '')).strip() == 'A'
            return jsonify({
                'success': True, 
                'nombre': usuario.get('nombre', 'Usuario'),
                'es_admin': es_admin
            })
        return jsonify({'success': False, 'message': 'Usuario no encontrado'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error servidor: {str(e)}'})

@app.route('/api/get_solicitudes', methods=['GET'])
def api_get_solicitudes():
    try:
        solicitudes = load_csv('solicitudes.csv')
        solicitudes.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify({'success': True, 'solicitudes': solicitudes})
    except:
        return jsonify({'success': True, 'solicitudes': []})

@app.route('/api/create_solicitud', methods=['POST'])
def api_create_solicitud():
    try:
        data = request.json
        tipo = data.get('tipo', 'Devolución')
        
        # Validaciones según tipo
        if tipo == 'Devolución':
            if not data.get('cliente') or not data.get('monto'):
                return jsonify({'success': False, 'message': 'Faltan datos de devolución'})
        elif not data.get('motivo'):
             return jsonify({'success': False, 'message': 'Debe detallar la solicitud'})

        import random
        nuevo_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(10,99)}"
        
        nueva = {
            'id': nuevo_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'solicitante_nombre': data.get('solicitante', ''),
            'tipo': tipo,
            'cliente_nombre': data.get('cliente', ''),
            'banco': data.get('banco', ''),
            'rut': data.get('rut', ''),
            'email': data.get('email', ''),
            'monto': data.get('monto', '0'),
            'motivo': data.get('motivo', ''),
            'estado': 'Pendiente',
            'comentario_cierre': ''
        }
        
        fieldnames = ['id', 'timestamp', 'solicitante_nombre', 'tipo', 'cliente_nombre', 
                      'banco', 'rut', 'email', 'monto', 'motivo', 'estado', 'comentario_cierre']
        
        filepath = os.path.join(DATA_DIR, 'solicitudes.csv')
        file_exists = os.path.exists(filepath)
        
        with open(filepath, 'a', newline='', encoding=app_config.CSV_ENCODING) as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=app_config.CSV_DELIMITER)
            if not file_exists: w.writeheader()
            w.writerow(nueva)
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'})

@app.route('/api/close_solicitud', methods=['POST'])
def api_close_solicitud():
    try:
        sid = request.json.get('id')
        comment = request.json.get('comentario', '').strip()
        
        if not comment: return jsonify({'success': False, 'message': 'Comentario obligatorio'})
        
        solicitudes = load_csv('solicitudes.csv')
        for s in solicitudes:
            if s.get('id') == sid:
                s['estado'] = 'Cerrado'
                s['comentario_cierre'] = comment
                break
        
        fieldnames = ['id', 'timestamp', 'solicitante_nombre', 'tipo', 'cliente_nombre', 
                      'banco', 'rut', 'email', 'monto', 'motivo', 'estado', 'comentario_cierre']
        save_csv('solicitudes.csv', solicitudes, fieldnames)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error cerrando: {str(e)}'})

# =============================================================================
# FIN SISTEMA DE SOLICITUDES
# =============================================================================
# =============================================================================
# FIN DEL ARCHIVO - Esto debe ir al final
# =============================================================================

if __name__ == '__main__':
    app.run(
        debug=app_config.DEBUG, 
        host='0.0.0.0', 
        port=5005
    )

