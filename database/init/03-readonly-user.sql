DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'mcp_readonly') THEN
        CREATE ROLE mcp_readonly LOGIN;
    END IF;
END
$$;

ALTER ROLE mcp_readonly SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE demo TO mcp_readonly;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON TABLES TO mcp_readonly;
