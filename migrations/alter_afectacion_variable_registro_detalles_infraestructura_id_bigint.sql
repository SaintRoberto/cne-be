BEGIN;

ALTER TABLE public.afectacion_variable_registro_detalles
    ALTER COLUMN infraestructura_id TYPE BIGINT
    USING infraestructura_id::BIGINT;

COMMIT;
