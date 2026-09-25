-- ==============================================================================
-- PathBridge 2.0 Database Schema (PostgreSQL / Supabase)
-- ==============================================================================

-- Enable UUID and vector extensions if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "vector"; -- Enable if using pgvector

-- 1. Profiles Table
CREATE TABLE IF NOT EXISTS profiles (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    education JSONB DEFAULT '[]'::jsonb,
    skills JSONB DEFAULT '{}'::jsonb,
    experience JSONB DEFAULT '[]'::jsonb,
    projects JSONB DEFAULT '[]'::jsonb,
    career_interests JSONB DEFAULT '[]'::jsonb,
    preferred_locations JSONB DEFAULT '[]'::jsonb,
    preferred_work_modes JSONB DEFAULT '[]'::jsonb,
    preferred_opportunity_types JSONB DEFAULT '[]'::jsonb,
    resume_text TEXT,
    profile_strength NUMERIC(5,2) DEFAULT 75.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);

-- 2. Opportunities Table
CREATE TABLE IF NOT EXISTS opportunities (
    id VARCHAR(64) PRIMARY KEY,
    company VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(255) NOT NULL,
    work_mode VARCHAR(64) NOT NULL,
    opportunity_type VARCHAR(64) NOT NULL,
    skills JSONB DEFAULT '[]'::jsonb,
    eligibility TEXT,
    salary VARCHAR(255),
    deadline VARCHAR(255),
    source_url VARCHAR(1024),
    application_url VARCHAR(1024),
    company_domain VARCHAR(255),
    verification_status VARCHAR(64) DEFAULT 'VERIFIED',
    verification_score NUMERIC(5,2) DEFAULT 90.0,
    company_logo_color VARCHAR(64),
    company_initial VARCHAR(16),
    duration VARCHAR(64),
    responsibilities JSONB DEFAULT '[]'::jsonb,
    requirements JSONB DEFAULT '[]'::jsonb,
    benefits JSONB DEFAULT '[]'::jsonb,
    verification_checks JSONB DEFAULT '[]'::jsonb,
    posted_days_ago NUMERIC(5,2) DEFAULT 1.0,
    embedding JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_opportunities_company ON opportunities(company);
CREATE INDEX IF NOT EXISTS idx_opportunities_work_mode ON opportunities(work_mode);
CREATE INDEX IF NOT EXISTS idx_opportunities_opp_type ON opportunities(opportunity_type);
CREATE INDEX IF NOT EXISTS idx_opportunities_verif_status ON opportunities(verification_status);

-- 3. Recommendations Table
CREATE TABLE IF NOT EXISTS recommendations (
    id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(64) NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    opportunity_id VARCHAR(64) NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    match_score NUMERIC(5,2) NOT NULL,
    skills_score NUMERIC(5,2) NOT NULL,
    experience_score NUMERIC(5,2) NOT NULL,
    education_score NUMERIC(5,2) NOT NULL,
    preference_score NUMERIC(5,2) NOT NULL,
    career_alignment_score NUMERIC(5,2) NOT NULL,
    matched_skills JSONB DEFAULT '[]'::jsonb,
    skill_gaps JSONB DEFAULT '[]'::jsonb,
    explanation TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_profile_opportunity UNIQUE (profile_id, opportunity_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_profile ON recommendations(profile_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_opportunity ON recommendations(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_match_score ON recommendations(match_score DESC);

-- 4. Verifications Table
CREATE TABLE IF NOT EXISTS verifications (
    id VARCHAR(64) PRIMARY KEY,
    opportunity_id VARCHAR(64) NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    status VARCHAR(64) NOT NULL, -- VERIFIED, NEEDS_REVIEW, SUSPICIOUS
    confidence NUMERIC(5,2) NOT NULL,
    signals JSONB DEFAULT '{}'::jsonb,
    risk_factors JSONB DEFAULT '[]'::jsonb,
    explanation TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verifications_opportunity ON verifications(opportunity_id);

-- 5. Applications Table
CREATE TABLE IF NOT EXISTS applications (
    id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(64) NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    opportunity_id VARCHAR(64) NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    status VARCHAR(64) NOT NULL DEFAULT 'APPLIED', -- SAVED, APPLIED, INTERVIEW, REJECTED, OFFER
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    metadata_info JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(profile_id);
CREATE INDEX IF NOT EXISTS idx_applications_opportunity ON applications(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
