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

if __name__ == '__main__':
    app.run(
        debug=app_config.DEBUG, 
        host='0.0.0.0', 
        port=5000
    )