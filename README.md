# JetSur

Sistema web para la **gestión de venta de viajes**, desarrollado con Django.

> Estado: en desarrollo. Actualmente el sistema cubre la gestión de ventas de viajes; se irán incorporando nuevos módulos.

## Características

- Gestión de viajes y de su venta.
- Autenticación de usuarios con distintos roles (administrador y cajero).
- Configuración segura mediante variables de entorno.

## Tecnologías

- Python 3.13
- Django
- MySQL
- django-environ

## Estructura del proyecto

```
ISJetsur/
├── JetSur/          # Configuración del proyecto (settings, urls, wsgi/asgi)
├── usuarios/        # Gestión de usuarios y roles
├── viajes/          # Gestión de viajes y ventas
├── static/          # Archivos estáticos
├── templates/       # Plantillas globales
├── manage.py
├── requirements.txt
└── .env             # Variables de entorno (no se versiona)
```

## Requisitos previos

- Python 3.13 o superior
- MySQL en ejecución
- Git

## Instalación

1. **Clonar el repositorio**

   ```bash
   git clone <URL-DEL-REPOSITORIO>
   cd ISJetsur
   ```

2. **Crear y activar el entorno virtual**

   Windows (PowerShell):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Linux / macOS:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar las dependencias**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar las variables de entorno**

   Crea un archivo llamado .env en la raíz del proyecto, es decir, en la carpeta ISJetsur/ al mismo nivel que manage.py y README.md (no dentro de JetSur/, viajes/ ni usuarios/):

   ```env
   SECRET_KEY=cambia-esto-por-una-clave-generada
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=nombre_tu_db
   DB_USER=tu_user
   DB_PASSWORD=tu_contraseña
   DB_HOST=tu_host
   DB_PORT=3306
   DB_CONN_MAX_AGE=60
   ```

   
   Para generar una `SECRET_KEY` nueva:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
   ```


7. **Iniciar el servidor de desarrollo**

   ```bash
   python manage.py runserver
   ```

   La aplicación estará disponible en http://127.0.0.1:8000/

## Usuarios de prueba

Solo para entorno de desarrollo:

| Rol           | Correo             | Contraseña  |
|---------------|--------------------|-------------|
| Administrador | admin@jetsur.cl    | `admin123`  |
| Cajero        | cajero@jetsur.cl   | `cajero123` |

> **Importante:** estas credenciales son únicamente de prueba. Elimínalas o cámbialas antes de desplegar en producción.

