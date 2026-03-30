-- ============================================================================
-- Zinnia Axion Database Schema Initialization
-- ============================================================================
-- This script creates all tables in the 'zinnia' schema for PostgreSQL
-- Run this as the 'axion' user or superuser after creating the zinnia schema
-- ============================================================================

-- Step 1: Ensure the zinnia schema exists
CREATE SCHEMA IF NOT EXISTS zinnia;

-- Step 2: Create all tables in the zinnia schema

-- Users table
CREATE TABLE IF NOT EXISTS zinnia.users (
    id SERIAL NOT NULL PRIMARY KEY,
    lan_id VARCHAR(128) NOT NULL UNIQUE,
    email VARCHAR(256),
    display_name VARCHAR(256),
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

-- Create indexes on users
CREATE INDEX IF NOT EXISTS ix_users_lan_id ON zinnia.users(lan_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON zinnia.users(email);

-- Teams table
CREATE TABLE IF NOT EXISTS zinnia.teams (
    id SERIAL NOT NULL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    parent_team_id INTEGER REFERENCES zinnia.teams(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

-- Create indexes on teams
CREATE INDEX IF NOT EXISTS ix_teams_parent_team_id ON zinnia.teams(parent_team_id);

-- Memberships table
CREATE TABLE IF NOT EXISTS zinnia.memberships (
    id SERIAL NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES zinnia.users(id),
    team_id INTEGER NOT NULL REFERENCES zinnia.teams(id),
    active BOOLEAN NOT NULL DEFAULT true,
    start_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_at TIMESTAMP WITHOUT TIME ZONE
);

-- Create indexes on memberships
CREATE INDEX IF NOT EXISTS ix_memberships_user_id ON zinnia.memberships(user_id);
CREATE INDEX IF NOT EXISTS ix_memberships_team_id ON zinnia.memberships(team_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_memberships_one_active_per_user 
    ON zinnia.memberships(user_id) WHERE active = true;

-- Managers table
CREATE TABLE IF NOT EXISTS zinnia.managers (
    user_id INTEGER NOT NULL PRIMARY KEY REFERENCES zinnia.users(id),
    team_id INTEGER NOT NULL REFERENCES zinnia.teams(id)
);

-- Create indexes on managers
CREATE INDEX IF NOT EXISTS ix_managers_team_id ON zinnia.managers(team_id);

-- Tracker Device Tokens table
CREATE TABLE IF NOT EXISTS zinnia.tracker_device_tokens (
    id SERIAL NOT NULL PRIMARY KEY,
    token_hash VARCHAR(256) NOT NULL,
    user_id INTEGER REFERENCES zinnia.users(id),
    team_id INTEGER NOT NULL REFERENCES zinnia.teams(id),
    description VARCHAR(256),
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    rotated_from_id INTEGER REFERENCES zinnia.tracker_device_tokens(id)
);

-- Create indexes on tracker_device_tokens
CREATE INDEX IF NOT EXISTS ix_tracker_device_tokens_token_hash ON zinnia.tracker_device_tokens(token_hash);

-- Team Change Requests table
CREATE TABLE IF NOT EXISTS zinnia.team_change_requests (
    id SERIAL NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES zinnia.users(id),
    from_team_id INTEGER REFERENCES zinnia.teams(id),
    to_team_id INTEGER NOT NULL REFERENCES zinnia.teams(id),
    requested_by INTEGER NOT NULL REFERENCES zinnia.users(id),
    approved_by INTEGER REFERENCES zinnia.users(id),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITHOUT TIME ZONE
);

-- Create indexes on team_change_requests
CREATE INDEX IF NOT EXISTS ix_team_change_requests_user_id ON zinnia.team_change_requests(user_id);

-- Telemetry Events table
CREATE TABLE IF NOT EXISTS zinnia.telemetry_events (
    id SERIAL NOT NULL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL DEFAULT 'default',
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    app_name VARCHAR(256) NOT NULL DEFAULT 'unknown',
    window_title VARCHAR(1024) NOT NULL DEFAULT '',
    keystroke_count INTEGER NOT NULL DEFAULT 0,
    mouse_clicks INTEGER NOT NULL DEFAULT 0,
    mouse_distance FLOAT NOT NULL DEFAULT 0.0,
    idle_seconds FLOAT NOT NULL DEFAULT 0.0,
    distraction_visible BOOLEAN NOT NULL DEFAULT false
);

-- Create indexes on telemetry_events
CREATE INDEX IF NOT EXISTS ix_telemetry_events_user_id ON zinnia.telemetry_events(user_id);
CREATE INDEX IF NOT EXISTS ix_telemetry_events_timestamp ON zinnia.telemetry_events(timestamp);
CREATE INDEX IF NOT EXISTS ix_telemetry_events_user_timestamp ON zinnia.telemetry_events(user_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_telemetry_events_app_name ON zinnia.telemetry_events(app_name);

-- Audit Log table
CREATE TABLE IF NOT EXISTS zinnia.audit_log (
    id SERIAL NOT NULL PRIMARY KEY,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    actor VARCHAR(256) NOT NULL DEFAULT 'unknown',
    action VARCHAR(128) NOT NULL,
    target_user VARCHAR(128),
    ip_address VARCHAR(64),
    user_agent VARCHAR(512),
    detail VARCHAR(1024),
    actor_user_id INTEGER REFERENCES zinnia.users(id),
    actor_team_id INTEGER REFERENCES zinnia.teams(id),
    target_team_id INTEGER REFERENCES zinnia.teams(id),
    request_id VARCHAR(64),
    extra_data TEXT
);

-- Create indexes on audit_log
CREATE INDEX IF NOT EXISTS ix_audit_log_timestamp ON zinnia.audit_log(timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_log_action ON zinnia.audit_log(action);
CREATE INDEX IF NOT EXISTS ix_audit_log_request_id ON zinnia.audit_log(request_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_actor_timestamp ON zinnia.audit_log(actor, timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_log_action_timestamp ON zinnia.audit_log(action, timestamp);

-- Alembic version table (for migration tracking)
CREATE TABLE IF NOT EXISTS zinnia.alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- Step 3: Insert initial migration version
INSERT INTO zinnia.alembic_version (version_num) VALUES ('init') ON CONFLICT DO NOTHING;

-- ============================================================================
-- Demo Data (Optional - comment out if not needed)
-- ============================================================================

-- Insert demo teams
INSERT INTO zinnia.teams (name, parent_team_id, created_at) VALUES
    ('Engineering', NULL, NOW()),
    ('Lifecad', (SELECT id FROM zinnia.teams WHERE name = 'Engineering'), NOW()),
    ('Axion', (SELECT id FROM zinnia.teams WHERE name = 'Lifecad'), NOW()),
    ('Fast', (SELECT id FROM zinnia.teams WHERE name = 'Engineering'), NOW())
ON CONFLICT (name) DO NOTHING;

-- Insert demo users
INSERT INTO zinnia.users (lan_id, email, display_name, role, created_at, updated_at) VALUES
    ('nikhil', 'nikhil@company.local', 'Nikhil Saxena', 'manager', NOW(), NOW()),
    ('demo_manager', 'wasim@company.local', 'Wasim Shaikh', 'manager', NOW(), NOW()),
    ('atharva_mgr', 'atharva@company.local', 'Atharva Tippe', 'manager', NOW(), NOW()),
    ('punit', 'punit@company.local', 'Punit Joshi', 'manager', NOW(), NOW()),
    ('Atharva', 'atharva.user@company.local', 'Atharva', 'user', NOW(), NOW()),
    ('Wasim', 'wasim.user@company.local', 'Wasim', 'user', NOW(), NOW()),
    ('kumarlu', 'kumarlu@company.local', 'Kumarlu', 'user', NOW(), NOW())
ON CONFLICT (lan_id) DO NOTHING;

-- Insert demo managers
INSERT INTO zinnia.managers (user_id, team_id) VALUES
    ((SELECT id FROM zinnia.users WHERE lan_id = 'nikhil'), (SELECT id FROM zinnia.teams WHERE name = 'Engineering')),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'demo_manager'), (SELECT id FROM zinnia.teams WHERE name = 'Lifecad')),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'atharva_mgr'), (SELECT id FROM zinnia.teams WHERE name = 'Axion')),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'punit'), (SELECT id FROM zinnia.teams WHERE name = 'Fast'))
ON CONFLICT (user_id) DO NOTHING;

-- Insert demo memberships
INSERT INTO zinnia.memberships (user_id, team_id, active, start_at, end_at) VALUES
    ((SELECT id FROM zinnia.users WHERE lan_id = 'nikhil'), (SELECT id FROM zinnia.teams WHERE name = 'Engineering'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'demo_manager'), (SELECT id FROM zinnia.teams WHERE name = 'Lifecad'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'atharva_mgr'), (SELECT id FROM zinnia.teams WHERE name = 'Axion'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'punit'), (SELECT id FROM zinnia.teams WHERE name = 'Fast'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'Atharva'), (SELECT id FROM zinnia.teams WHERE name = 'Axion'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'Wasim'), (SELECT id FROM zinnia.teams WHERE name = 'Lifecad'), true, NOW(), NULL),
    ((SELECT id FROM zinnia.users WHERE lan_id = 'kumarlu'), (SELECT id FROM zinnia.teams WHERE name = 'Fast'), true, NOW(), NULL)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Verification
-- ============================================================================

-- Display created tables
SELECT 'Tables created successfully!' as status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'zinnia' 
ORDER BY table_name;

-- Display row counts
SELECT 
    'zinnia.users' as table_name,
    COUNT(*) as row_count
FROM zinnia.users
UNION ALL
SELECT 'zinnia.teams', COUNT(*) FROM zinnia.teams
UNION ALL
SELECT 'zinnia.memberships', COUNT(*) FROM zinnia.memberships
UNION ALL
SELECT 'zinnia.managers', COUNT(*) FROM zinnia.managers
UNION ALL
SELECT 'zinnia.telemetry_events', COUNT(*) FROM zinnia.telemetry_events
UNION ALL
SELECT 'zinnia.audit_log', COUNT(*) FROM zinnia.audit_log;

-- ============================================================================
-- Done!
-- ============================================================================
