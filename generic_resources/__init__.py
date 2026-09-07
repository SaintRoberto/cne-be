from flask import Blueprint


generic_resources_bp = Blueprint(
    "generic_resources",
    __name__,
    url_prefix="/api",
)

from generic_resources import routes  # noqa: E402, F401
