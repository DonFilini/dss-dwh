WHENEVER SQLERROR EXIT FAILURE ROLLBACK
CREATE TABLE customer_refresh_log (
    run_id RAW(16) DEFAULT SYS_GUID() NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR2(10 CHAR) NOT NULL,
    error_code NUMBER,
    CONSTRAINT pk_customer_refresh_log PRIMARY KEY (run_id),
    CONSTRAINT chk_customer_refresh_status
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);
