import hmac
from functools import wraps

from flask import current_app, jsonify, request

from reportes import reportes_bp


def powerbi_basic_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected_username = current_app.config.get("POWERBI_API_USERNAME", "")
        expected_password = current_app.config.get("POWERBI_API_PASSWORD", "")
        if not expected_username or not expected_password:
            current_app.logger.error(
                "POWERBI_API_USERNAME y POWERBI_API_PASSWORD no estan configurados"
            )
            return jsonify(error="La integracion de Power BI no esta configurada"), 503

        authorization = request.authorization
        valid = (
            authorization is not None
            and authorization.type.lower() == "basic"
            and hmac.compare_digest(authorization.username or "", expected_username)
            and hmac.compare_digest(authorization.password or "", expected_password)
        )
        if not valid:
            response = jsonify(error="Credenciales de Power BI invalidas")
            response.status_code = 401
            response.headers["WWW-Authenticate"] = 'Basic realm="CNE Power BI"'
            return response
        return view(*args, **kwargs)

    return wrapped


def _call_dashboard_view(endpoint: str, **path_parameters):
    dashboard_view = current_app.view_functions.get(
        f"generic_resources.{endpoint}"
    )
    if dashboard_view is None:
        current_app.logger.error("Endpoint interno no encontrado: %s", endpoint)
        return jsonify(error="Fuente de datos no disponible"), 503

    # Los endpoints del dashboard ya contienen la consulta y serializacion.
    # Se omite solo su decorador JWT porque esta ruta ya valido Basic Auth.
    unwrapped_view = getattr(dashboard_view, "__wrapped__", dashboard_view)
    return unwrapped_view(**path_parameters)


@reportes_bp.get("/eventos")
@powerbi_basic_required
def powerbi_events():
    """Eventos del dashboard para Power BI
    ---
    tags: [Reportes Power BI]
    security:
      - BasicAuth: []
    parameters:
      - in: query
        name: provincia_id
        type: integer
        required: false
    responses:
      200:
        description: Eventos con sus datos relacionados
      401:
        description: Credenciales invalidas
    """
    return _call_dashboard_view("eventos_list")


@reportes_bp.get("/afectaciones/provincias")
@powerbi_basic_required
def powerbi_affectations_by_province():
    """Resumen de afectaciones por provincia para Power BI
    ---
    tags: [Reportes Power BI]
    security:
      - BasicAuth: []
    parameters:
      - in: query
        name: fecha_inicio
        type: string
        format: date
        required: false
      - in: query
        name: fecha_fin
        type: string
        format: date
        required: false
      - in: query
        name: emergencia_id
        type: integer
        required: false
      - in: query
        name: provincia_id
        type: integer
        required: false
      - in: query
        name: canton_id
        type: integer
        required: false
    responses:
      200:
        description: Resumen de eventos y afectaciones por provincia
      401:
        description: Credenciales invalidas
    """
    return _call_dashboard_view("eventos_afectaciones_by_provincia")


@reportes_bp.get("/afectacion-variable-registros")
@powerbi_basic_required
def powerbi_affectation_records():
    """Registros de afectaciones para Power BI
    ---
    tags: [Reportes Power BI]
    security:
      - BasicAuth: []
    responses:
      200:
        description: Registros de variables de afectacion
      401:
        description: Credenciales invalidas
    """
    return _call_dashboard_view("afectacion_variable_registros_list")


@reportes_bp.get(
    "/variables-afectacion/mesa-grupo/<int:mesa_grupo_id>/coe/<int:coe_id>"
)
@powerbi_basic_required
def powerbi_affectation_variables(mesa_grupo_id: int, coe_id: int):
    """Variables de afectacion configuradas para Power BI
    ---
    tags: [Reportes Power BI]
    security:
      - BasicAuth: []
    parameters:
      - in: path
        name: mesa_grupo_id
        type: integer
        required: true
      - in: path
        name: coe_id
        type: integer
        required: true
    responses:
      200:
        description: Variables de afectacion configuradas
      401:
        description: Credenciales invalidas
    """
    return _call_dashboard_view(
        "afectacion_variables_by_mesa_grupo_coe",
        mesa_grupo_id=mesa_grupo_id,
        coe_id=coe_id,
    )
