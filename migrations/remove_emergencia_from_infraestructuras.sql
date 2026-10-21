BEGIN;

ALTER TABLE public.infraestructuras
    DROP COLUMN IF EXISTS emergencia_id;

COMMIT;
