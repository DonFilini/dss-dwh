WHENEVER SQLERROR EXIT FAILURE ROLLBACK
CREATE UNIQUE INDEX ux_customer_day
    ON mv_customer_day (name_key, phone_key, event_day);
BEGIN
    DBMS_STATS.GATHER_TABLE_STATS(
        ownname => USER, tabname => 'MV_CUSTOMER_DAY', cascade => TRUE
    );
END;
/
GRANT SELECT ON mv_customer_day TO api_user;
