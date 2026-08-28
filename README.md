# CNE Backend

Backend REST desde cero en Flask, organizado por módulos siguiendo el patrón del
repositorio `simulacro-backend`: un archivo raíz de aplicación, autenticación,
modelos y esquemas, más una carpeta/Blueprint independiente por dominio.

Incluye PostgreSQL, SQLAlchemy, JWT, hashing bcrypt mediante Passlib, validación
Marshmallow, CORS, Swagger UI y pruebas de integración.

## Estructura

```text
cne-be/
├── app.py                  # Application factory, CORS, Swagger y comandos CLI
├── auth.py                 # Contraseñas, JWT y decorador de autenticación
├── config.py               # Configuración mediante variables de entorno
├── extensions.py           # Instancia desacoplada de SQLAlchemy
├── models.py               # Modelos Usuario y Riesgo
├── schemas.py              # Validación y serialización Marshmallow
├── database_schema.sql     # Esquema PostgreSQL alternativo
├── usuarios/
│   ├── __init__.py         # Blueprint
│   └── routes.py           # Registro, login y CRUD de usuarios
├── riesgos/
│   ├── __init__.py         # Blueprint
│   └── routes.py           # CRUD de riesgos por propietario
├── utils/
│   └── validation.py       # Validación JSON compartida
├── tests/
│   └── test_api.py         # Pruebas sin PostgreSQL externo
└── requirements.txt
```

## Instalación local

Requiere Python 3.10+ y PostgreSQL.

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y completa allí la conexión PostgreSQL y la clave
JWT. La aplicación carga ese archivo automáticamente mediante `python-dotenv`.
El archivo `.env` está excluido de Git y no debe compartirse. Como mínimo, cambia
`JWT_SECRET_KEY` fuera de desarrollo.

En PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:TU_PASSWORD@localhost:5432/proceso_electoral"
$env:JWT_SECRET_KEY = "una-clave-larga-y-aleatoria"
flask --app app init-db
python app.py
```

La API estará disponible en `http://localhost:5000`:

- Swagger UI: `http://localhost:5000/apidocs/`
- Especificación JSON: `http://localhost:5000/apispec_1.json`
- Health check: `http://localhost:5000/api/health`

## Flujo de autenticación

1. Registra un usuario con `POST /api/usuarios/register`.
2. También puedes obtener un token con `POST /api/usuarios/login`.
3. En Swagger pulsa **Authorize** y pega únicamente el token, sin `Bearer`.
4. Consume los endpoints protegidos de usuarios y riesgos.

Ejemplo de registro:

```bash
curl -X POST http://localhost:5000/api/usuarios/register \
  -H "Content-Type: application/json" \
  -d '{
    "usuario": "admin",
    "correo": "admin@example.com",
    "clave": "ClaveSegura123",
    "nombre": "Administrador"
  }'
```

Ejemplo de riesgo:

```bash
curl -X POST http://localhost:5000/api/riesgos \
  -H "Content-Type: application/json" \
  -H "Authorization: TU_TOKEN" \
  -d '{
    "titulo": "Pérdida de datos",
    "descripcion": "Falla del almacenamiento principal",
    "probabilidad": 0.4,
    "impacto": 0.9,
    "estado": "abierto"
  }'
```

## Endpoints principales

| Método | Ruta | Autenticación | Descripción |
|---|---|---:|---|
| GET | `/api/health` | No | Estado de la API |
| POST | `/api/usuarios/register` | No | Registro y emisión de JWT |
| POST | `/api/usuarios/login` | No | Inicio de sesión |
| GET | `/api/usuarios/me` | Sí | Usuario autenticado |
| GET | `/api/usuarios` | Sí | Listar usuarios |
| GET/PUT/PATCH/DELETE | `/api/usuarios/{id}` | Sí | CRUD de usuario |
| GET/POST | `/api/riesgos` | Sí | Listar y crear riesgos propios |
| GET/PUT/PATCH/DELETE | `/api/riesgos/{id}` | Sí | CRUD de riesgo propio |

## Pruebas

Las pruebas usan SQLite en memoria, por lo que no necesitan levantar PostgreSQL:

```bash
python -m unittest discover -v
```

## Agregar un nuevo módulo

Crea una carpeta con `__init__.py` para declarar el Blueprint y `routes.py` para
sus endpoints; después registra el Blueprint dentro de `create_app()` en
`app.py`. Los modelos compartidos van en `models.py` y sus esquemas Marshmallow
en `schemas.py`, conservando el mismo patrón modular.
