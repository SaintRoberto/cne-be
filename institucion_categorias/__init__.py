from flask import Blueprint


institucion_categorias_bp = Blueprint(
    "institucion_categorias",
    __name__,
    url_prefix="/api/institucion-categorias",
)

from institucion_categorias import routes  # noqa: E402, F401
