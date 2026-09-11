from flask import Blueprint


infraestructuras_bp = Blueprint(
    "infraestructuras_import",
    __name__,
    url_prefix="/api/infraestructuras",
)


from infraestructuras import routes  # noqa: E402,F401
