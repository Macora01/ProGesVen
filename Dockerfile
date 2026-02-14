# Usamos una imagen oficial de Python ligera
FROM python:3.9-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos el archivo de requisitos primero para aprovechar el caché de Docker
COPY requirements.txt .

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código de la aplicación al contenedor
COPY . .

# Exponemos el puerto por el que correrá la aplicación Flask
# Gunicorn se encargará de escuchar en este puerto
EXPOSE 5000

# Usamos Gunicorn como servidor web para producción, es mucho más robusto que el servidor de desarrollo de Flask
# El comando ejecuta la aplicación definida como 'app' dentro del archivo 'app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "app:app"]
