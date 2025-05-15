-- Create database
CREATE DATABASE football_manager;

-- Connect to database
\c football_manager;

-- Create tables
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    team VARCHAR(100) NOT NULL,
    position VARCHAR(50),
    access_level VARCHAR(20) NOT NULL,
    photo_path VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- GDPR consent tracking
CREATE TABLE consent_records (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    consent_type VARCHAR(50) NOT NULL,
    consent_given BOOLEAN NOT NULL,
    consent_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    consent_version VARCHAR(20) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Data retention policy
CREATE TABLE data_retention (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    retention_period INTEGER NOT NULL, -- in days
    retention_reason TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Create indexes
CREATE INDEX idx_players_player_id ON players(player_id);
CREATE INDEX idx_consent_records_player_id ON consent_records(player_id);
CREATE INDEX idx_data_retention_player_id ON data_retention(player_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for updated_at
CREATE TRIGGER update_players_updated_at
    BEFORE UPDATE ON players
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

