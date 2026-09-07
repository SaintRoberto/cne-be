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
├── models.py               # Modelos de las tablas vigentes
├── schemas.py              # Validación y serialización Marshmallow
├── database_schema.sql     # Esquema PostgreSQL alternativo
├── usuarios/
│   ├── __init__.py         # Blueprint
│   └── routes.py           # Registro, login y CRUD de usuarios
├── institucion_categorias/ # CRUD de categorías de institución
├── instituciones/          # CRUD de instituciones
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
4. Consume los endpoints protegidos de usuarios, instituciones y categorías.

Ejemplo de registro:

```bash
curl -X POST http://localhost:5000/api/usuarios/register \
  -H "Content-Type: application/json" \
  -d '{
    "institucion_id": 1,
    "usuario": "admin",
    "correo": "admin@example.com",
    "clave": "ClaveSegura123",
    "nombres": "Usuario",
    "apellidos": "Administrador",
    "cedula": "0102030405",
    "celular": "0999999999"
  }'
```

Ejemplo de categoría de institución:

```bash
curl -X POST http://localhost:5000/api/institucion-categorias \
  -H "Content-Type: application/json" \
  -H "Authorization: TU_TOKEN" \
  -d '{
    "nombre": "Gobierno central",
    "descripcion": "Instituciones del gobierno central"
  }'
```

## Endpoints principales

| Método | Ruta | Autenticación | Descripción |
|---|---|---:|---|
| GET | `/api/health` | No | Estado de la API |
| POST | `/api/usuarios` o `/api/usuarios/register` | No | Crear usuario y emitir JWT |
| POST | `/api/usuarios/login` | No | Inicio de sesión |
| GET | `/api/usuarios/me` | Sí | Usuario autenticado |
| GET | `/api/usuarios` | Sí | Listar usuarios |
| GET/PUT/PATCH/DELETE | `/api/usuarios/{id}` | Sí | CRUD de usuario |
| GET/POST | `/api/institucion-categorias` | Sí | Listar y crear categorías |
| GET/PUT/PATCH/DELETE | `/api/institucion-categorias/{id}` | Sí | CRUD de categoría |
| GET/POST | `/api/instituciones` | Sí | Listar y crear instituciones |
| GET/PUT/PATCH/DELETE | `/api/instituciones/{id}` | Sí | CRUD de institución |

Los recursos creados por reflexión de tablas tienen el mismo patrón CRUD:
`GET/POST /api/{recurso}` y `GET/PUT/PATCH/DELETE /api/{recurso}/{id}`.

Recursos disponibles:
`provincias`, `cantones`, `parroquias`, `evento-atencion-estados`,
`evento-categorias`, `evento-causas`, `evento-clases`, `evento-estados`,
`evento-fenomenos`, `evento-origenes`, `evento-subtipos`, `evento-tipos`,
`eventos`, `infraestructura-tipos` e `infraestructuras`.

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
