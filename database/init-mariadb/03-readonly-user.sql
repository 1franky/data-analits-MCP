CREATE USER IF NOT EXISTS 'mcp_readonly'@'%' IDENTIFIED BY 'local-only-placeholder-change-me';

GRANT SELECT, SHOW VIEW ON demo.* TO 'mcp_readonly'@'%';

FLUSH PRIVILEGES;
