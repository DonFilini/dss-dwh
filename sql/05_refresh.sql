-- Run once from ETL after BOTH source loads succeed; no concurrent runs.
WHENEVER OSERROR EXIT FAILURE ROLLBACK
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET TIMING ON
DECLARE
    v_run_id RAW(16) := SYS_GUID();
    v_error_code NUMBER;
BEGIN
    INSERT INTO customer_refresh_log (run_id, started_at, status)
    VALUES (v_run_id, SYSTIMESTAMP, 'RUNNING');
    COMMIT;
    BEGIN
        DBMS_MVIEW.REFRESH(
            list => 'APP.MV_CUSTOMER_DAY',
            method => 'C',
            atomic_refresh => TRUE
        );
    EXCEPTION
        WHEN OTHERS THEN
            v_error_code := SQLCODE;
            ROLLBACK;
            UPDATE customer_refresh_log
            SET finished_at = SYSTIMESTAMP,
                status = 'FAILED', error_code = v_error_code
            WHERE run_id = v_run_id;
            COMMIT;
            RAISE;
    END;
    UPDATE customer_refresh_log
    SET finished_at = SYSTIMESTAMP, status = 'SUCCESS'
    WHERE run_id = v_run_id;
    COMMIT;
END;
/
EXIT SUCCESS
