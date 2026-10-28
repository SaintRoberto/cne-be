from flask import Blueprint


reportes_bp = Blueprint("reportes", __name__, url_prefix="/api/reportes")

from reportes import routes  # noqa: E402, F401
