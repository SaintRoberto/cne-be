BEGIN;

CREATE OR REPLACE PROCEDURE sp_validar_looker_eventos_afectaciones(
    p_provincia_id INTEGER DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_columnas TEXT;
    v_sql TEXT;
BEGIN
    SELECT string_agg(
        format(
            'COALESCE(SUM(avr.cantidad) FILTER '
            '(WHERE avr.afectacion_variable_id = %s), 0)::BIGINT AS %I',
            av.id,
            av.nombre
        ),
        E',\n            '
        ORDER BY av.id
    )
    INTO v_columnas
    FROM afectacion_variables AS av;

    IF v_columnas IS NULL THEN
        RAISE EXCEPTION 'No existen registros en afectacion_variables';
    END IF;

    DROP TABLE IF EXISTS tmp_looker_eventos_afectaciones;

    v_sql := format(
        $query$
        CREATE TEMP TABLE tmp_looker_eventos_afectaciones
        ON COMMIT PRESERVE ROWS
        AS
        SELECT
            e.*,
            %s
        FROM eventos AS e
        LEFT JOIN afectacion_variable_registros AS avr
            ON avr.evento_id = e.id
        WHERE ($1 IS NULL OR e.provincia_id = $1)
        GROUP BY e.id
        $query$,
        v_columnas
    );

    EXECUTE v_sql USING p_provincia_id;
END;
$$;

COMMIT;
