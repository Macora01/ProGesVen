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
    return render_template('index.html')

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/api/search_product', methods=['POST'])
def api_search_product():
    code = request.json.get('code', '').strip().upper()
    
    # Validar formato del código
    if not (validate_factory_code(code, app_config) or validate_sales_code(code, app_config)):
        return jsonify({
            'success': False,
            'message': 'Formato de código inválido. Use código fábrica (3-8 caracteres) o código venta (BINNNNCC)'
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
    return render_template('events.html', bazares=bazares)

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

def get_sales_data_by_date_range(start_date, end_date):
    """Obtener datos de ventas para un rango de fechas específico"""
    total_sales = 0
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
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        daily_sales = 0
        daily_amount = 0
        daily_locations = set()
        
        # Buscar archivos de ventas de esta fecha
        for filename in os.listdir(SALES_DIR):
            if date_str in filename:
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
                            
                            # Limpiar y convertir precio
                            precio = str(row.get('precio', '0')).replace('$', '').replace('.', '').strip()
                            if precio.isdigit():
                                amount = int(precio)
                                total_amount += amount
                                daily_amount += amount
                            
                            # Estadísticas por producto
                            product_code = row.get('cod_venta') or row.get('cod_fabrica', '')
                            if product_code:
                                if product_code in product_sales:
                                    product_sales[product_code]['count'] += 1
                                    product_sales[product_code]['amount'] += amount
                                else:
                                    # Buscar información del producto
                                    productos = load_csv('productos.csv', fieldnames=['cod_fabrica', 'cod_venta', 'descripcion', 'precio'])
                                    product_info = next((p for p in productos if p.get('cod_fabrica') == product_code or p.get('cod_venta') == product_code), {})
                                    product_sales[product_code] = {
                                        'count': 1,
                                        'amount': amount,
                                        'description': product_info.get('descripcion', 'Producto no encontrado'),
                                        'price': product_info.get('precio', 0)
                                    }
                            
                            # Estadísticas por ubicación
                            if location in location_sales:
                                location_sales[location]['count'] += 1
                                location_sales[location]['amount'] += amount
                            else:
                                location_sales[location] = {
                                    'count': 1,
                                    'amount': amount
                                }
                                
                except Exception as e:
                    print(f"Error procesando {filename}: {e}")
        
        daily_data[date_str] = {
            'sales': daily_sales,
            'amount': daily_amount,
            'locations': len(daily_locations)
        }
        
        current_date += timedelta(days=1)
    
    # Ordenar productos por cantidad vendida
    top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:10]
    
    # Ordenar ubicaciones por monto
    sorted_locations = dict(sorted(location_sales.items(), key=lambda x: x[1]['amount'], reverse=True))
    
    return {
        'total_sales': total_sales,
        'total_amount': total_amount,
        'active_locations': len(locations_active),
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'daily_data': daily_data,
        'top_products': top_products,
        'location_sales': sorted_locations
    }

def get_period_data(period):
    """Obtener datos para períodos predefinidos"""
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
    
    return get_sales_data_by_date_range(start_date, end_date)

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
    
    if start_date and end_date:
        # Usar rango personalizado
        data = get_sales_data_by_date_range(start_date, end_date)
    else:
        # Usar período predefinido
        data = get_period_data(period)
    
    return jsonify(data)

# Mantener la ruta original del dashboard para compatibilidad
@app.route('/api/dashboard_data')
def api_dashboard_data():
    if not session.get('authorized'):
        return jsonify({'error': 'No autorizado'}), 403
    
    # Por defecto mostrar datos del día actual
    data = get_period_data('today')
    return jsonify(data)

# =============================================================================
# FIN DEL ARCHIVO - Esto debe ir al final
# =============================================================================

if __name__ == '__main__':
    app.run(
        debug=app_config.DEBUG, 
        host='0.0.0.0', 
        port=5000
    )

