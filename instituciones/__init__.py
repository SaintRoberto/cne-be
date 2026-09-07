from flask import Blueprint


instituciones_bp = Blueprint(
    "instituciones",
    __name__,
    url_prefix="/api/instituciones",
)

from instituciones import routes  # noqa: E402, F401
