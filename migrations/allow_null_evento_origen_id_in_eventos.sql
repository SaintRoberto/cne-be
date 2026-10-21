BEGIN;

ALTER TABLE public.eventos
    ALTER COLUMN evento_origen_id DROP NOT NULL;

COMMIT;
