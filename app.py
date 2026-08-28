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
        "description": "Backend Flask con autenticación JWT y gestión de riesgos.",
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
            "required": ["usuario", "correo", "clave", "nombre"],
            "properties": {
                "usuario": {"type": "string", "example": "admin"},
                "correo": {"type": "string", "example": "admin@example.com"},
                "clave": {"type": "string", "format": "password", "example": "ClaveSegura123"},
                "nombre": {"type": "string", "example": "Administrador"},
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
                "correo": {"type": "string"},
                "clave": {"type": "string", "format": "password"},
                "nombre": {"type": "string"},
                "activo": {"type": "boolean"},
            },
        },
        "RiskInput": {
            "type": "object",
            "required": ["titulo", "probabilidad", "impacto"],
            "properties": {
                "titulo": {"type": "string", "example": "Pérdida de datos"},
                "descripcion": {"type": "string"},
                "probabilidad": {"type": "number", "minimum": 0, "maximum": 1, "example": 0.4},
                "impacto": {"type": "number", "minimum": 0, "maximum": 1, "example": 0.9},
                "estado": {
                    "type": "string",
                    "enum": ["abierto", "en_progreso", "mitigado", "cerrado"],
                    "default": "abierto",
                },
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

    from riesgos import riesgos_bp
    from usuarios import usuarios_bp

    app.register_blueprint(usuarios_bp)
    app.register_blueprint(riesgos_bp)

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
