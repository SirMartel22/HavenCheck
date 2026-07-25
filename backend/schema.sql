CREATE TABLE IF NOT EXISTS hostels (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    location VARCHAR NOT NULL,
    price_naira INTEGER NOT NULL,
    amenities JSON NOT NULL,
    description TEXT NOT NULL,
    photo_url VARCHAR NULL,
    lat DOUBLE PRECISION NULL,
    lng DOUBLE PRECISION NULL,
    is_school_managed BOOLEAN NOT NULL DEFAULT FALSE,
    scam_risk_level VARCHAR NULL
);

CREATE INDEX IF NOT EXISTS ix_hostels_location ON hostels (location);

CREATE TABLE IF NOT EXISTS area_price_averages (
    id SERIAL PRIMARY KEY,
    location VARCHAR NOT NULL UNIQUE,
    avg_price_naira INTEGER NOT NULL,
    price_range_low INTEGER NOT NULL,
    price_range_high INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_area_price_averages_location ON area_price_averages (location);

CREATE TABLE IF NOT EXISTS utility_reports (
    id SERIAL PRIMARY KEY,
    hostel_id VARCHAR NOT NULL REFERENCES hostels(id) ON DELETE CASCADE,
    water_available BOOLEAN NOT NULL,
    electricity_issue BOOLEAN NOT NULL,
    comment TEXT NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_utility_reports_hostel_id ON utility_reports (hostel_id);

CREATE TABLE IF NOT EXISTS scam_transcripts (
    id SERIAL PRIMARY KEY,
    hostel_id VARCHAR NULL REFERENCES hostels(id) ON DELETE SET NULL,
    transcript_text TEXT NOT NULL,
    is_scam BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    hostel_id VARCHAR NULL REFERENCES hostels(id),
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id);
