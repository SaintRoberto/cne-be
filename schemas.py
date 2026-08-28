from marshmallow import Schema, fields, validate


EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
RISK_STATES = ("abierto", "en_progreso", "mitigado", "cerrado")


class RegisterSchema(Schema):
    usuario = fields.String(required=True, validate=validate.Length(min=3, max=80))
    correo = fields.String(
        required=True,
        validate=[validate.Length(max=255), validate.Regexp(EMAIL_PATTERN)],
    )
    clave = fields.String(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )
    nombre = fields.String(required=True, validate=validate.Length(min=2, max=120))


class LoginSchema(Schema):
    usuario = fields.String(required=True)
    clave = fields.String(required=True, load_only=True)


class UsuarioUpdateSchema(Schema):
    correo = fields.String(
        validate=[validate.Length(max=255), validate.Regexp(EMAIL_PATTERN)]
    )
    clave = fields.String(load_only=True, validate=validate.Length(min=8, max=128))
    nombre = fields.String(validate=validate.Length(min=2, max=120))
    activo = fields.Boolean()


class UsuarioResponseSchema(Schema):
    id = fields.Integer(dump_only=True)
    usuario = fields.String(dump_only=True)
    correo = fields.String(dump_only=True)
    nombre = fields.String(dump_only=True)
    activo = fields.Boolean(dump_only=True)
    creado_en = fields.DateTime(dump_only=True)
    actualizado_en = fields.DateTime(dump_only=True)


class RiesgoInputSchema(Schema):
    titulo = fields.String(required=True, validate=validate.Length(min=3, max=160))
    descripcion = fields.String(allow_none=True, validate=validate.Length(max=5000))
    probabilidad = fields.Float(required=True, validate=validate.Range(min=0, max=1))
    impacto = fields.Float(required=True, validate=validate.Range(min=0, max=1))
    estado = fields.String(
        load_default="abierto", validate=validate.OneOf(RISK_STATES)
    )


class RiesgoResponseSchema(Schema):
    id = fields.Integer(dump_only=True)
    titulo = fields.String(dump_only=True)
    descripcion = fields.String(dump_only=True, allow_none=True)
    probabilidad = fields.Float(dump_only=True)
    impacto = fields.Float(dump_only=True)
    nivel = fields.Float(dump_only=True)
    estado = fields.String(dump_only=True)
    propietario_id = fields.Integer(dump_only=True)
    creado_en = fields.DateTime(dump_only=True)
    actualizado_en = fields.DateTime(dump_only=True)


register_schema = RegisterSchema()
login_schema = LoginSchema()
usuario_update_schema = UsuarioUpdateSchema()
usuario_response_schema = UsuarioResponseSchema()
usuarios_response_schema = UsuarioResponseSchema(many=True)
riesgo_input_schema = RiesgoInputSchema()
riesgo_response_schema = RiesgoResponseSchema()
riesgos_response_schema = RiesgoResponseSchema(many=True)
