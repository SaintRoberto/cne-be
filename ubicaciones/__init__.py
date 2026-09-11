from flask import Blueprint


ubicaciones_bp = Blueprint("ubicaciones", __name__, url_prefix="/api/ubicaciones")

from ubicaciones import routes  # noqa: E402, F401
