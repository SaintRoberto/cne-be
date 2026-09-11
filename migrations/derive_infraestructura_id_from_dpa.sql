BEGIN;

LOCK TABLE public.infraestructuras IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.infraestructuras
        WHERE dpa IS NULL OR dpa !~ '^[0-9]{15}$'
    ) THEN
        RAISE EXCEPTION 'No se puede derivar el ID: existen DPA de infraestructura invalidos';
    END IF;
END
$$;

ALTER TABLE public.infraestructuras
    ALTER COLUMN id DROP IDENTITY IF EXISTS,
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN id TYPE BIGINT;

UPDATE public.infraestructuras
SET id = dpa::BIGINT
WHERE id IS DISTINCT FROM dpa::BIGINT;

ALTER TABLE public.infraestructuras
    DROP CONSTRAINT IF EXISTS ck_infraestructuras_id_dpa;

ALTER TABLE public.infraestructuras
    ADD CONSTRAINT ck_infraestructuras_id_dpa
    CHECK (id = dpa::BIGINT);

COMMIT;
