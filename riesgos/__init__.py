from flask import Blueprint


riesgos_bp = Blueprint("riesgos", __name__, url_prefix="/api/riesgos")

from riesgos import routes  # noqa: E402, F401
