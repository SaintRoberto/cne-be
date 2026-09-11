import os

import click
from flasgger import Swagger
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from extensions import db


SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "CNE API",
        "description": "Backend Flask con autenticación JWT y gestión institucional.",
        "version": "1.0.0",
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Pegue únicamente el token JWT (comienza con eyJ).",
        }
    },
    "definitions": {
        "RegisterInput": {
            "type": "object",
            "required": ["institucion_id", "usuario", "clave"],
            "properties": {
                "institucion_id": {"type": "integer", "example": 1},
                "usuario": {"type": "string", "example": "admin"},
                "correo": {"type": "string", "example": "admin@example.com"},
                "clave": {"type": "string", "format": "password", "example": "ClaveSegura123"},
                "nombres": {"type": "string", "example": "Usuario"},
                "apellidos": {"type": "string", "example": "Administrador"},
                "descripcion": {"type": "string"},
                "celular": {"type": "string"},
                "cedula": {"type": "string"},
                "aprobado": {"type": "boolean", "default": False},
                "activo": {"type": "boolean", "default": True},
                "creador": {"type": "string", "default": "Sistema"},
            },
        },
        "LoginInput": {
            "type": "object",
            "required": ["usuario", "clave"],
            "properties": {
                "usuario": {"type": "string", "example": "admin"},
                "clave": {"type": "string", "format": "password", "example": "ClaveSegura123"},
            },
        },
        "UserUpdateInput": {
            "type": "object",
            "properties": {
                "institucion_id": {"type": "integer"},
                "usuario": {"type": "string"},
                "correo": {"type": "string"},
                "clave": {"type": "string", "format": "password"},
                "nombres": {"type": "string"},
                "apellidos": {"type": "string"},
                "descripcion": {"type": "string"},
                "celular": {"type": "string"},
                "cedula": {"type": "string"},
                "aprobado": {"type": "boolean"},
                "activo": {"type": "boolean"},
                "modificador": {"type": "string"},
            },
        },
        "InstitutionCategoryInput": {
            "type": "object",
            "required": ["nombre"],
            "properties": {
                "nombre": {"type": "string", "example": "Gobierno central"},
                "descripcion": {"type": "string"},
                "activo": {"type": "boolean", "default": True},
            },
        },
        "InstitutionInput": {
            "type": "object",
            "required": ["nombre"],
            "properties": {
                "institucion_categoria_id": {"type": "integer"},
                "nombre": {"type": "string", "example": "Consejo Nacional Electoral"},
                "siglas": {"type": "string", "example": "CNE"},
                "observaciones": {"type": "string"},
                "activo": {"type": "boolean", "default": True},
            },
        },
    },
}


def create_app(config_override=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.from_mapping(config_override)

    db.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    from institucion_categorias import institucion_categorias_bp
    from instituciones import instituciones_bp
    from generic_resources import generic_resources_bp
    from infraestructuras import infraestructuras_bp
    from ubicaciones import ubicaciones_bp
    from usuarios import usuarios_bp

    app.register_blueprint(usuarios_bp)
    app.register_blueprint(institucion_categorias_bp)
    app.register_blueprint(instituciones_bp)
    app.register_blueprint(generic_resources_bp)
    app.register_blueprint(infraestructuras_bp)
    app.register_blueprint(ubicaciones_bp)

    @app.get("/api/health")
    def health():
        """Comprobar que la API está disponible
        ---
        tags: [Sistema]
        responses:
          200:
            description: La API está operativa
        """
        return jsonify(estado="OK", mensaje="API funcionando correctamente")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Recurso no encontrado"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Método no permitido"), 405

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception(
            "Error no controlado durante la petición",
            exc_info=getattr(error, "original_exception", error),
        )
        return jsonify(error="Error interno del servidor"), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        db.create_all()
        click.echo("Tablas creadas correctamente.")

    Swagger(
        app,
        template=SWAGGER_TEMPLATE,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec_1",
                    "route": "/apispec_1.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/apidocs/",
        },
    )
    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
