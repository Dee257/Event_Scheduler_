# Collaborative Event Scheduling API

A RESTful API backend for an event scheduling application with advanced collaborative features, built using Python and a relational database. Supports user authentication, role-based access control, recurring events, event sharing with granular permissions and versioning with rollback.

---

## Features

- **User Authentication** with JWT tokens and token revocation (blocklist)
- **Role-Based Access Control** for events with roles: Owner, Editor, Viewer
- **Event Management**: CRUD operations, recurring events support
- **Collaboration**: Share events with different permission levels
- **Versioning**: Track event changes, rollback, and view changelogs/diffs
- **Audit Trails**: Track who modified events and when
- **Efficient querying** with indexes and JSON data storage for versions

---

## Getting Started

### Prerequisites

- Python 3.8+
- MySQL
- pip (Python package installer)

### .env File

- FLASK_ENV=development
- SECRET_KEY=supersecretkey
- JWT_SECRET_KEY=jwtsecretkey
- SQLALCHEMY_DATABASE_URI=mysql+mysqlconnector://username:password@localhost/event_db

### DATABASE SCHEMA
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Token Blocklist for JWT revocation
CREATE TABLE token_blocklist (
    id SERIAL PRIMARY KEY,
    jti VARCHAR(36) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    access_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    refresh_expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Events table
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    location VARCHAR(255),
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern VARCHAR(255),
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Event Permissions table
CREATE TABLE event_permissions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    username VARCHAR(80) NOT NULL
);

-- Event Versions table
CREATE TABLE event_versions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    version_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modified_by VARCHAR(120),
    updated_by VARCHAR(128)
);

-- Indexes for performance
CREATE INDEX idx_event_versions_event_id ON event_versions(event_id);
CREATE INDEX idx_event_permissions_event_user ON event_permissions(event_id, user_id);



