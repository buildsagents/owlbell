-- ============================================================================
-- Owlbell — Supabase-compatible PostgreSQL Schema
-- Generated from SQLAlchemy models (base, enums, tenant, user, call, ai,
-- business, integration, operations)
--
-- Target: Supabase-hosted PostgreSQL 15+
-- Notes:
--   • Uses gen_random_uuid() (pgcrypto extension, preloaded by Supabase)
--   • Row-Level Security enabled on every table with tenant_isolation policy
--   • CREATE INDEX CONCURRENTLY excluded inside transactions — use
--     a separate migration or run indexes outside BEGIN/COMMIT blocks
-- ============================================================================

-- ─── Extensions ─────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- trigram similarity for search

-- ─── Helper: UUIDv4 generation ──────────────────────────────────────────────
-- gen_random_uuid() from pgcrypto already returns a v4 UUID.
-- Kept as a named function for clarity and migration compatibility.

CREATE OR REPLACE FUNCTION public.gen_uuid_v4()
RETURNS uuid
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT gen_random_uuid();
$$;

COMMENT ON FUNCTION public.gen_uuid_v4() IS 'Alias for gen_random_uuid(); returns a random UUID v4.';

-- ─── Helper: updated_at trigger ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.set_updated_at() IS 'Automatically sets updated_at to now() on row update.';

-- ─── Helper: auto-populate created_at / updated_at ──────────────────────────

CREATE OR REPLACE FUNCTION public.set_created_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.created_at IS NULL THEN
    NEW.created_at = now();
  END IF;
  IF NEW.updated_at IS NULL THEN
    NEW.updated_at = now();
  END IF;
  RETURN NEW;
END;
$$;

-- ─── Helper: full-text search vector trigger for transcripts ────────────────

CREATE OR REPLACE FUNCTION public.transcript_search_vector_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', COALESCE(NEW.text_normalized, NEW.text)), 'A');
  RETURN NEW;
END;
$$;

-- ─── Helper: full-text search vector trigger for FAQ entries ────────────────

CREATE OR REPLACE FUNCTION public.faq_search_vector_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', COALESCE(NEW.question, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(NEW.answer, '')), 'B');
  RETURN NEW;
END;
$$;

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

DO $$ BEGIN
  CREATE TYPE public.call_direction AS ENUM ('inbound', 'outbound');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.call_status AS ENUM (
    'queued', 'ringing', 'answered', 'active', 'on_hold',
    'transferred', 'completed', 'failed', 'voicemail', 'no_answer'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.call_result AS ENUM (
    'success', 'voicemail_left', 'no_answer', 'busy',
    'failed', 'transferred', 'hangup', 'error'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.call_leg_type AS ENUM (
    'caller', 'ai_agent', 'human_agent', 'voicemail', 'conference'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.message_role AS ENUM ('system', 'assistant', 'user', 'tool');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.message_type AS ENUM (
    'text', 'tool_call', 'tool_result', 'transfer', 'voicemail', 'hangup'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.message_status AS ENUM ('pending', 'processing', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.appointment_status AS ENUM (
    'pending', 'confirmed', 'cancelled', 'completed', 'no_show'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.routing_type AS ENUM (
    'auto_attendant', 'time_based', 'intent_based', 'caller_id', 'default'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.routing_action AS ENUM (
    'answer', 'transfer', 'voicemail', 'reject', 'queue', 'menu'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.webhook_event AS ENUM (
    'call.started', 'call.ended', 'call.transcribed',
    'appointment.created', 'appointment.updated',
    'voicemail.received', 'message.received'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.notification_channel AS ENUM (
    'email', 'sms', 'webhook', 'slack', 'push', 'in_app'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.integration_provider AS ENUM (
    'google_calendar', 'outlook_calendar', 'zapier', 'make',
    'hubspot', 'salesforce', 'slack', 'teams'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.plan_tier AS ENUM ('free', 'starter', 'professional', 'enterprise');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('super_admin', 'admin', 'manager', 'agent', 'viewer');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.tenant_status AS ENUM (
    'pending', 'active', 'limited', 'suspended', 'terminated', 'purged'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.day_of_week AS ENUM (
    'monday', 'tuesday', 'wednesday', 'thursday',
    'friday', 'saturday', 'sunday'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.ai_model AS ENUM (
    'llama3.1:8b', 'llama3.1:70b', 'mistral:7b', 'mixtral:8x7b', 'custom'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.voice_type AS ENUM (
    'piper_default', 'piper_male_1', 'piper_female_1', 'piper_custom'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.transcript_source AS ENUM (
    'whisper_local', 'whisper_api', 'deepgram', 'assembly'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.intent_type AS ENUM (
    'appointment', 'question', 'complaint', 'transfer_request',
    'voicemail_request', 'information', 'emergency',
    'sales', 'support', 'general'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.actor_type AS ENUM (
    'user', 'system', 'api_key', 'ai_agent', 'integration'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- TABLE: tenants — root of multi-tenancy
-- ============================================================================

CREATE TABLE public.tenants (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                VARCHAR(63)  NOT NULL,
  name                VARCHAR(255) NOT NULL,
  status              public.tenant_status NOT NULL DEFAULT 'active',
  plan_tier           public.plan_tier     NOT NULL DEFAULT 'free',
  plan_expires_at     TIMESTAMPTZ,

  -- Business profile
  business_name       VARCHAR(255),
  business_phone      VARCHAR(30),
  business_email      VARCHAR(255),
  business_timezone   VARCHAR(50)  NOT NULL DEFAULT 'America/New_York',
  business_address    TEXT,
  business_website    VARCHAR(255),
  industry            VARCHAR(100),

  -- AI configuration
  ai_model            public.ai_model NOT NULL DEFAULT 'llama3.1:8b',
  ai_temperature      NUMERIC(3,2) NOT NULL DEFAULT 0.7,
  ai_max_tokens       INT          NOT NULL DEFAULT 256,
  ai_system_prompt    TEXT,
  voice_type          public.voice_type  NOT NULL DEFAULT 'piper_default',
  voice_speed         NUMERIC(3,2) NOT NULL DEFAULT 1.0,
  stt_model           public.transcript_source NOT NULL DEFAULT 'whisper_local',
  stt_language        VARCHAR(10)  NOT NULL DEFAULT 'en',

  -- Call handling
  max_call_duration   INT          NOT NULL DEFAULT 600,
  voicemail_enabled   BOOLEAN      NOT NULL DEFAULT true,
  voicemail_greeting  TEXT,
  after_hours_action  VARCHAR(20)  NOT NULL DEFAULT 'voicemail',
  concurrent_calls_max INT         NOT NULL DEFAULT 5,

  -- Customization
  greeting_message    TEXT,
  hold_music_url      VARCHAR(500),
  transfer_number     VARCHAR(30),

  -- Metadata
  config_json         JSONB        NOT NULL DEFAULT '{}',
  features_json       JSONB        NOT NULL DEFAULT '{}',

  -- Soft delete
  deleted_at          TIMESTAMPTZ,

  -- Timestamps
  created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT slug_format          CHECK (slug ~ '^[a-z0-9-]+$'),
  CONSTRAINT temperature_range    CHECK (ai_temperature BETWEEN 0.0 AND 2.0),
  CONSTRAINT voice_speed_range    CHECK (voice_speed BETWEEN 0.5 AND 2.0),
  CONSTRAINT uq_tenant_slug       UNIQUE (slug)
);

CREATE INDEX idx_tenants_status      ON public.tenants (status);
CREATE INDEX idx_tenants_plan_tier   ON public.tenants (plan_tier);
CREATE INDEX idx_tenants_deleted_at  ON public.tenants (deleted_at);

-- ============================================================================
-- TABLE: tenant_configs — per-tenant configuration settings
-- ============================================================================

CREATE TABLE public.tenant_configs (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL UNIQUE,
  ai_settings           JSONB NOT NULL DEFAULT '{}',
  routing_rules         JSONB NOT NULL DEFAULT '{}',
  notification_settings JSONB NOT NULL DEFAULT '{}',
  integrations          JSONB NOT NULL DEFAULT '{}',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT fk_tenant_configs_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: users — staff members with dashboard access
-- ============================================================================

CREATE TABLE public.users (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,
  email             VARCHAR(255)  NOT NULL,
  password_hash     VARCHAR(255)  NOT NULL,
  first_name        VARCHAR(100)  NOT NULL,
  last_name         VARCHAR(100)  NOT NULL,
  role              public.user_role NOT NULL DEFAULT 'viewer',
  phone             VARCHAR(30),
  avatar_url        VARCHAR(500),

  -- Status
  is_active         BOOLEAN       NOT NULL DEFAULT true,
  last_login_at     TIMESTAMPTZ,
  email_verified_at TIMESTAMPTZ,

  -- Preferences
  timezone          VARCHAR(50)   NOT NULL DEFAULT 'America/New_York',
  notification_prefs JSONB        NOT NULL DEFAULT '{
    "email_call_summary": true,
    "email_voicemail": true,
    "email_appointment": true,
    "sms_call_summary": false,
    "dashboard_sound": true
  }',

  -- API access
  api_key_hash      VARCHAR(255),

  -- Soft delete
  deleted_at        TIMESTAMPTZ,

  -- Timestamps
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_user_email_per_tenant UNIQUE (tenant_id, email),

  CONSTRAINT fk_users_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_users_tenant_id   ON public.users (tenant_id);
CREATE INDEX idx_users_email       ON public.users (email);
CREATE INDEX idx_users_deleted_at  ON public.users (deleted_at);
CREATE INDEX idx_users_role        ON public.users (role);

-- ============================================================================
-- TABLE: calls — primary call session records
-- ============================================================================

CREATE TABLE public.calls (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID          NOT NULL,
  call_sid              VARCHAR(64)   NOT NULL,
  parent_call_id        UUID,

  -- Direction & routing
  direction             public.call_direction NOT NULL,
  caller_number         VARCHAR(30)   NOT NULL,
  caller_name           VARCHAR(255),
  caller_id_hash        VARCHAR(64),
  destination_number    VARCHAR(30)   NOT NULL,

  -- Status & result
  status                public.call_status NOT NULL DEFAULT 'queued',
  result                public.call_result,

  -- Timing
  started_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
  answered_at           TIMESTAMPTZ,
  ended_at              TIMESTAMPTZ,
  duration_seconds      INT,
  talk_time_seconds     INT           NOT NULL DEFAULT 0,

  -- AI interaction summary
  ai_handled            BOOLEAN       NOT NULL DEFAULT false,
  ai_model_used         public.ai_model,
  transcript_summary    TEXT,
  sentiment_score       NUMERIC(4,3),
  intent_detected       VARCHAR(100),

  -- Transfer info
  transferred_to        VARCHAR(30),
  transfer_reason       VARCHAR(255),

  -- Quality metrics
  audio_quality_mos     NUMERIC(3,2),
  stt_confidence_avg    NUMERIC(4,3),
  llm_tokens_used       INT           NOT NULL DEFAULT 0,
  tts_chars_used        INT           NOT NULL DEFAULT 0,

  -- Voicemail
  voicemail_left        BOOLEAN       NOT NULL DEFAULT false,
  voicemail_duration    INT,

  -- Cost & billing
  estimated_cost        NUMERIC(10,6) NOT NULL DEFAULT 0.0,

  -- Metadata
  tags                  JSONB         NOT NULL DEFAULT '[]',
  metadata_json         JSONB         NOT NULL DEFAULT '{}',

  -- Partitioning
  partition_key         VARCHAR(7),

  -- Timestamps
  created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_call_sid UNIQUE (call_sid),

  CONSTRAINT fk_calls_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_calls_parent
    FOREIGN KEY (parent_call_id) REFERENCES public.calls(id) ON DELETE SET NULL
);

CREATE INDEX idx_calls_tenant_id     ON public.calls (tenant_id);
CREATE INDEX idx_calls_call_sid      ON public.calls (call_sid);
CREATE INDEX idx_calls_status        ON public.calls (status);
CREATE INDEX idx_calls_direction     ON public.calls (direction);
CREATE INDEX idx_calls_started_at    ON public.calls (started_at);
CREATE INDEX idx_calls_created_at    ON public.calls (created_at);
CREATE INDEX idx_calls_partition_key ON public.calls (partition_key);
CREATE INDEX idx_calls_caller_number ON public.calls (caller_number);
CREATE INDEX idx_calls_parent_call   ON public.calls (parent_call_id);

-- ============================================================================
-- TABLE: call_legs — individual call participants
-- ============================================================================

CREATE TABLE public.call_legs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,
  call_id           UUID          NOT NULL,

  -- Leg identity
  leg_type          VARCHAR(20)   NOT NULL,
  leg_index         INT           NOT NULL DEFAULT 1,
  display_name      VARCHAR(255),
  phone_number      VARCHAR(30),
  user_id           UUID,

  -- Media
  sip_call_id       VARCHAR(128),
  local_sdp         TEXT,
  remote_sdp        TEXT,
  rtp_local_ip      VARCHAR(45),
  rtp_local_port    INT,

  -- Timing
  joined_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),
  left_at           TIMESTAMPTZ,
  duration_seconds  INT,
  status            VARCHAR(20)   NOT NULL DEFAULT 'active',

  -- Timestamps
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_call_legs_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_call_legs_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE,
  CONSTRAINT fk_call_legs_user
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_call_legs_tenant_id ON public.call_legs (tenant_id);
CREATE INDEX idx_call_legs_call_id   ON public.call_legs (call_id);
CREATE INDEX idx_call_legs_user_id   ON public.call_legs (user_id);
CREATE INDEX idx_call_legs_leg_type  ON public.call_legs (leg_type);
CREATE INDEX idx_call_legs_status    ON public.call_legs (status);

-- ============================================================================
-- TABLE: recordings — audio recording metadata
-- ============================================================================

CREATE TABLE public.recordings (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,
  call_id             UUID           NOT NULL,
  call_leg_id         UUID,

  -- File info
  file_path           VARCHAR(500)   NOT NULL,
  file_size_bytes     BIGINT         NOT NULL,
  file_format         VARCHAR(10)    NOT NULL DEFAULT 'wav',
  duration_seconds    NUMERIC(8,2)   NOT NULL,
  sample_rate         INT            NOT NULL DEFAULT 16000,
  channels            INT            NOT NULL DEFAULT 1,

  -- Storage
  storage_backend     VARCHAR(20)    NOT NULL DEFAULT 'local',
  storage_bucket      VARCHAR(100),
  storage_key         VARCHAR(500),

  -- Access control
  is_deleted          BOOLEAN        NOT NULL DEFAULT false,
  deleted_at          TIMESTAMPTZ,
  delete_after_days   INT,

  -- Public access
  access_url          VARCHAR(1000),
  access_expires_at   TIMESTAMPTZ,

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_recordings_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_recordings_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE,
  CONSTRAINT fk_recordings_call_leg
    FOREIGN KEY (call_leg_id) REFERENCES public.call_legs(id) ON DELETE SET NULL
);

CREATE INDEX idx_recordings_tenant_id   ON public.recordings (tenant_id);
CREATE INDEX idx_recordings_call_id     ON public.recordings (call_id);
CREATE INDEX idx_recordings_call_leg_id ON public.recordings (call_leg_id);
CREATE INDEX idx_recordings_deleted_at  ON public.recordings (deleted_at);
CREATE INDEX idx_recordings_created_at  ON public.recordings (created_at);

-- ============================================================================
-- TABLE: transcripts — speech-to-text output segments
-- ============================================================================

CREATE TABLE public.transcripts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,
  call_id           UUID          NOT NULL,

  -- Source
  source            public.transcript_source NOT NULL DEFAULT 'whisper_local',
  model_version     VARCHAR(50),
  language          VARCHAR(10)   NOT NULL DEFAULT 'en',

  -- Timing
  segment_start     NUMERIC(8,3)  NOT NULL,
  segment_end       NUMERIC(8,3)  NOT NULL,

  -- Content
  speaker           VARCHAR(20)   NOT NULL DEFAULT 'unknown',
  text              TEXT          NOT NULL,
  text_normalized   TEXT,

  -- Confidence
  confidence        NUMERIC(4,3),
  words_json        JSONB,

  -- Full-text search
  search_vector     TSVECTOR,

  -- Timestamps (no updated_at — transcripts are immutable)
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_transcripts_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_transcripts_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE,
  CONSTRAINT segment_timing CHECK (segment_end > segment_start)
);

CREATE INDEX idx_transcripts_tenant_id  ON public.transcripts (tenant_id);
CREATE INDEX idx_transcripts_call_id    ON public.transcripts (call_id);
CREATE INDEX idx_transcripts_source     ON public.transcripts (source);
CREATE INDEX idx_transcripts_speaker    ON public.transcripts (speaker);
CREATE INDEX idx_transcripts_created_at ON public.transcripts (created_at);
CREATE INDEX idx_transcripts_search     ON public.transcripts USING GIN (search_vector);

-- FTS trigger
CREATE TRIGGER trg_transcript_search_vector
  BEFORE INSERT OR UPDATE ON public.transcripts
  FOR EACH ROW EXECUTE FUNCTION public.transcript_search_vector_update();

-- ============================================================================
-- TABLE: conversations — AI conversation threads
-- ============================================================================

CREATE TABLE public.conversations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID          NOT NULL,
  call_id             UUID          NOT NULL,

  -- Conversation metadata
  turn_count          INT           NOT NULL DEFAULT 0,
  topic_category      VARCHAR(100),
  summary             TEXT,
  satisfaction_score  NUMERIC(4,3),

  -- Resolution
  resolved            BOOLEAN,
  resolution_type     VARCHAR(50),
  follow_up_required  BOOLEAN       NOT NULL DEFAULT false,

  -- Timestamps
  created_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_conversation_per_call UNIQUE (call_id),

  CONSTRAINT fk_conversations_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_conversations_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_conversations_tenant_id ON public.conversations (tenant_id);
CREATE INDEX idx_conversations_call_id   ON public.conversations (call_id);

-- ============================================================================
-- TABLE: messages — individual conversation messages
-- ============================================================================

CREATE TABLE public.messages (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,
  conversation_id   UUID          NOT NULL,
  call_id           UUID          NOT NULL,

  -- Content
  role              public.message_role NOT NULL,
  message_type      public.message_type NOT NULL DEFAULT 'text',
  content           TEXT          NOT NULL,
  content_json      JSONB,

  -- LLM metadata
  llm_model         public.ai_model,
  llm_temperature   NUMERIC(3,2),
  tokens_prompt     INT           NOT NULL DEFAULT 0,
  tokens_completion INT           NOT NULL DEFAULT 0,
  tokens_total      INT,
  latency_ms        INT,

  -- Sequence
  sequence_number   INT           NOT NULL,

  -- Timestamps (no updated_at — messages are immutable)
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_messages_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_messages_conversation
    FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE,
  CONSTRAINT fk_messages_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_tenant_id      ON public.messages (tenant_id);
CREATE INDEX idx_messages_conversation   ON public.messages (conversation_id);
CREATE INDEX idx_messages_call_id        ON public.messages (call_id);
CREATE INDEX idx_messages_role           ON public.messages (role);
CREATE INDEX idx_messages_message_type   ON public.messages (message_type);
CREATE INDEX idx_messages_sequence       ON public.messages (conversation_id, sequence_number);
CREATE INDEX idx_messages_created_at     ON public.messages (created_at);

-- ============================================================================
-- TABLE: prompts — system prompts and prompt templates
-- ============================================================================

CREATE TABLE public.prompts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Identity
  name                VARCHAR(100)   NOT NULL,
  description         TEXT,
  prompt_type         VARCHAR(30)    NOT NULL,

  -- Content
  content             TEXT           NOT NULL,
  variables_json      JSONB          NOT NULL DEFAULT '[]',

  -- Versioning
  version             INT            NOT NULL DEFAULT 1,
  is_active           BOOLEAN        NOT NULL DEFAULT true,

  -- Usage
  use_count           INT            NOT NULL DEFAULT 0,
  avg_response_score  NUMERIC(4,3),

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT fk_prompts_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT prompt_type_valid CHECK (
    prompt_type IN ('system', 'greeting', 'transfer', 'voicemail',
                    'closing', 'tool_call', 'custom')
  )
);

CREATE INDEX idx_prompts_tenant_id   ON public.prompts (tenant_id);
CREATE INDEX idx_prompts_prompt_type ON public.prompts (prompt_type);
CREATE INDEX idx_prompts_is_active   ON public.prompts (is_active);
CREATE INDEX idx_prompts_created_at  ON public.prompts (created_at);

-- ============================================================================
-- TABLE: prompt_versions — immutable versioned prompts (PromptManager)
-- ============================================================================

CREATE TABLE public.prompt_versions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID           NOT NULL,

  prompt_type       VARCHAR(30)    NOT NULL,
  version_number    INT            NOT NULL,
  name              VARCHAR(150)   NOT NULL,
  content           TEXT           NOT NULL,
  variables_json    JSONB          NOT NULL DEFAULT '{}',

  -- Lifecycle
  status            VARCHAR(20)    NOT NULL DEFAULT 'draft',
  is_active         BOOLEAN        NOT NULL DEFAULT false,

  -- A/B test linkage
  ab_test_group     VARCHAR(1),
  ab_test_id        UUID,

  -- Performance
  times_used        INT            NOT NULL DEFAULT 0,
  avg_call_rating   NUMERIC(4,3),

  -- Provenance
  created_by        UUID,
  notes             TEXT,

  created_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),
  activated_at      TIMESTAMPTZ,

  CONSTRAINT fk_prompt_versions_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT prompt_version_status_valid CHECK (
    status IN ('draft', 'active', 'archived', 'ab_test')
  )
);

CREATE INDEX idx_prompt_versions_tenant_id ON public.prompt_versions (tenant_id);
CREATE INDEX idx_prompt_versions_type      ON public.prompt_versions (tenant_id, prompt_type);
CREATE INDEX idx_prompt_versions_active    ON public.prompt_versions (tenant_id, prompt_type, is_active);
CREATE INDEX idx_prompt_versions_ab_test   ON public.prompt_versions (ab_test_id);

-- ============================================================================
-- TABLE: prompt_ab_tests — split tests between two prompt versions
-- ============================================================================

CREATE TABLE public.prompt_ab_tests (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID           NOT NULL,

  name                 VARCHAR(150)   NOT NULL,
  description          TEXT,
  prompt_type          VARCHAR(30)    NOT NULL,

  variant_a_id         UUID           NOT NULL,
  variant_b_id         UUID           NOT NULL,
  split_percentage     INT            NOT NULL DEFAULT 50,

  is_active            BOOLEAN        NOT NULL DEFAULT true,
  started_at           TIMESTAMPTZ    NOT NULL DEFAULT now(),
  ended_at             TIMESTAMPTZ,
  winning_variant      VARCHAR(1),

  -- Accumulated results
  total_participants   INT            NOT NULL DEFAULT 0,
  variant_a_calls      INT            NOT NULL DEFAULT 0,
  variant_b_calls      INT            NOT NULL DEFAULT 0,
  variant_a_avg_rating NUMERIC(4,3),
  variant_b_avg_rating NUMERIC(4,3),

  CONSTRAINT fk_prompt_ab_tests_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_prompt_ab_tests_tenant_id ON public.prompt_ab_tests (tenant_id);
CREATE INDEX idx_prompt_ab_tests_active    ON public.prompt_ab_tests (tenant_id, is_active);

-- ============================================================================
-- TABLE: onboarding_pipelines — per-client onboarding progress
-- ============================================================================

CREATE TABLE public.onboarding_pipelines (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID           NOT NULL,
  tenant_name   VARCHAR(150)   NOT NULL,
  tenant_email  VARCHAR(255)   NOT NULL,
  created_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_onboarding_pipelines_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_onboarding_pipelines_tenant_id ON public.onboarding_pipelines (tenant_id);

-- ============================================================================
-- TABLE: onboarding_steps — ordered steps within an onboarding pipeline
-- ============================================================================

CREATE TABLE public.onboarding_steps (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id      UUID           NOT NULL,
  tenant_id        UUID           NOT NULL,

  step_id          VARCHAR(50)    NOT NULL,
  name             VARCHAR(150)   NOT NULL,
  description      TEXT           NOT NULL,
  step_order       INT            NOT NULL,

  auto_completes   BOOLEAN        NOT NULL DEFAULT false,
  requires_action  BOOLEAN        NOT NULL DEFAULT false,
  estimated_days   INT            NOT NULL DEFAULT 1,

  status           VARCHAR(20)    NOT NULL DEFAULT 'pending',
  completed_at     TIMESTAMPTZ,
  notes            TEXT,
  assignee         VARCHAR(150),

  CONSTRAINT fk_onboarding_steps_pipeline
    FOREIGN KEY (pipeline_id) REFERENCES public.onboarding_pipelines(id) ON DELETE CASCADE,
  CONSTRAINT fk_onboarding_steps_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_onboarding_steps_pipeline_id ON public.onboarding_steps (pipeline_id);
CREATE INDEX idx_onboarding_steps_tenant_id   ON public.onboarding_steps (tenant_id);

-- ============================================================================
-- TABLE: onboarding_emails — post-sale onboarding email sequence
-- ============================================================================

CREATE TABLE public.onboarding_emails (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   UUID,
  tenant_id     UUID           NOT NULL,

  email_id      VARCHAR(120)   NOT NULL,
  trigger_step  VARCHAR(50)    NOT NULL,
  subject       VARCHAR(500)   NOT NULL,
  template      VARCHAR(80)    NOT NULL,
  delay_hours   INT            NOT NULL DEFAULT 0,

  status        VARCHAR(20)    NOT NULL DEFAULT 'pending',
  sent_at       TIMESTAMPTZ,
  delivered_at  TIMESTAMPTZ,
  opened_at     TIMESTAMPTZ,
  error         TEXT,

  CONSTRAINT fk_onboarding_emails_pipeline
    FOREIGN KEY (pipeline_id) REFERENCES public.onboarding_pipelines(id) ON DELETE CASCADE,
  CONSTRAINT fk_onboarding_emails_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_onboarding_emails_pipeline_id ON public.onboarding_emails (pipeline_id);
CREATE INDEX idx_onboarding_emails_tenant_id   ON public.onboarding_emails (tenant_id);

-- ============================================================================
-- TABLE: tool_calls — AI tool/function invocations
-- ============================================================================

CREATE TABLE public.tool_calls (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,
  call_id           UUID          NOT NULL,
  message_id        UUID,

  -- Tool info
  tool_name         VARCHAR(100)  NOT NULL,
  tool_version      VARCHAR(20)   NOT NULL DEFAULT '1.0',

  -- Input / output
  arguments_json    JSONB         NOT NULL DEFAULT '{}',
  result_json       JSONB,
  error_json        JSONB,

  -- Execution
  status            VARCHAR(20)   NOT NULL DEFAULT 'pending',
  started_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
  completed_at      TIMESTAMPTZ,
  duration_ms       INT,

  -- Timestamps (no updated_at — tool call records are immutable)
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_tool_calls_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_tool_calls_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE,
  CONSTRAINT fk_tool_calls_message
    FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE SET NULL
);

CREATE INDEX idx_tool_calls_tenant_id ON public.tool_calls (tenant_id);
CREATE INDEX idx_tool_calls_call_id   ON public.tool_calls (call_id);
CREATE INDEX idx_tool_calls_message   ON public.tool_calls (message_id);
CREATE INDEX idx_tool_calls_tool_name ON public.tool_calls (tool_name);
CREATE INDEX idx_tool_calls_status    ON public.tool_calls (status);
CREATE INDEX idx_tool_calls_created   ON public.tool_calls (created_at);

-- ============================================================================
-- TABLE: appointments — appointment bookings
-- ============================================================================

CREATE TABLE public.appointments (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,
  call_id             UUID,

  -- Caller info
  caller_number       VARCHAR(30)    NOT NULL,
  caller_name         VARCHAR(255),

  -- Appointment details
  title               VARCHAR(255)   NOT NULL DEFAULT 'Appointment',
  description         TEXT,
  status              public.appointment_status NOT NULL DEFAULT 'pending',

  -- Timing
  scheduled_date      DATE           NOT NULL,
  start_time          TIME           NOT NULL,
  end_time            TIME           NOT NULL,
  timezone            VARCHAR(50)    NOT NULL DEFAULT 'America/New_York',

  -- Location / type
  appointment_type    VARCHAR(50)    NOT NULL DEFAULT 'in_person',
  location            VARCHAR(500),

  -- Attendee
  staff_user_id       UUID,
  staff_name          VARCHAR(255),

  -- Confirmation
  confirmed_at        TIMESTAMPTZ,
  confirmed_by        VARCHAR(20),
  reminder_sent_at    TIMESTAMPTZ,

  -- Cancellation
  cancelled_at        TIMESTAMPTZ,
  cancellation_reason TEXT,

  -- Calendar sync
  external_id         VARCHAR(255),
  external_provider   public.integration_provider,
  sync_status         VARCHAR(20)    NOT NULL DEFAULT 'pending',
  sync_error          TEXT,

  -- Metadata
  metadata_json       JSONB          NOT NULL DEFAULT '{}',

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT fk_appointments_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_appointments_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE SET NULL,
  CONSTRAINT fk_appointments_staff
    FOREIGN KEY (staff_user_id) REFERENCES public.users(id) ON DELETE SET NULL,
  CONSTRAINT time_order CHECK (end_time > start_time)
);

CREATE INDEX idx_appointments_tenant_id     ON public.appointments (tenant_id);
CREATE INDEX idx_appointments_call_id       ON public.appointments (call_id);
CREATE INDEX idx_appointments_staff_user    ON public.appointments (staff_user_id);
CREATE INDEX idx_appointments_status        ON public.appointments (status);
CREATE INDEX idx_appointments_scheduled     ON public.appointments (scheduled_date);
CREATE INDEX idx_appointments_created_at    ON public.appointments (created_at);
CREATE INDEX idx_appointments_sync_status   ON public.appointments (sync_status);
CREATE INDEX idx_appointments_external_id   ON public.appointments (external_id);

-- ============================================================================
-- TABLE: routing_rules — call routing configuration
-- ============================================================================

CREATE TABLE public.routing_rules (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Rule identity
  name                VARCHAR(255)   NOT NULL,
  description         TEXT,
  priority            INT            NOT NULL DEFAULT 100,

  -- Matching conditions
  rule_type           public.routing_type NOT NULL,
  conditions_json     JSONB          NOT NULL DEFAULT '{}',

  -- Action
  action              public.routing_action NOT NULL,
  action_config_json  JSONB          NOT NULL DEFAULT '{}',

  -- Status
  is_active           BOOLEAN        NOT NULL DEFAULT true,
  effective_from      TIMESTAMPTZ    NOT NULL DEFAULT now(),
  effective_to        TIMESTAMPTZ,

  -- Stats
  match_count         INT            NOT NULL DEFAULT 0,

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_rule_priority UNIQUE (tenant_id, priority),

  CONSTRAINT fk_routing_rules_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_routing_rules_tenant_id  ON public.routing_rules (tenant_id);
CREATE INDEX idx_routing_rules_priority   ON public.routing_rules (priority);
CREATE INDEX idx_routing_rules_is_active  ON public.routing_rules (is_active);
CREATE INDEX idx_routing_rules_rule_type  ON public.routing_rules (rule_type);
CREATE INDEX idx_routing_rules_effective  ON public.routing_rules (effective_from, effective_to);

-- ============================================================================
-- TABLE: faq_entries — FAQ knowledge base
-- ============================================================================

CREATE TABLE public.faq_entries (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               UUID           NOT NULL,

  -- Content
  question                TEXT           NOT NULL,
  answer                  TEXT           NOT NULL,
  category                VARCHAR(100)   NOT NULL DEFAULT 'general',
  tags_json               JSONB          NOT NULL DEFAULT '[]',

  -- Variants
  question_variants_json  JSONB          NOT NULL DEFAULT '[]',

  -- AI enhancement
  embeddings_json         JSONB,

  -- Full-text search
  search_vector           TSVECTOR,

  -- Usage stats
  use_count               INT            NOT NULL DEFAULT 0,
  helpful_count           INT            NOT NULL DEFAULT 0,
  last_used_at            TIMESTAMPTZ,

  -- Status
  is_active               BOOLEAN        NOT NULL DEFAULT true,
  deleted_at              TIMESTAMPTZ,

  -- Timestamps
  created_at              TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_faq_entries_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_faq_entries_tenant_id    ON public.faq_entries (tenant_id);
CREATE INDEX idx_faq_entries_category     ON public.faq_entries (category);
CREATE INDEX idx_faq_entries_is_active    ON public.faq_entries (is_active);
CREATE INDEX idx_faq_entries_deleted_at   ON public.faq_entries (deleted_at);
CREATE INDEX idx_faq_entries_use_count    ON public.faq_entries (use_count DESC);
CREATE INDEX idx_faq_entries_search       ON public.faq_entries USING GIN (search_vector);

-- FTS trigger
CREATE TRIGGER trg_faq_search_vector
  BEFORE INSERT OR UPDATE ON public.faq_entries
  FOR EACH ROW EXECUTE FUNCTION public.faq_search_vector_update();

-- ============================================================================
-- TABLE: business_hours — operating hours per tenant
-- ============================================================================

CREATE TABLE public.business_hours (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,

  -- Day & hours
  day_of_week       VARCHAR(10)   NOT NULL,
  open_time         TIME          NOT NULL,
  close_time        TIME          NOT NULL,
  is_closed         BOOLEAN       NOT NULL DEFAULT false,

  -- Override
  timezone          VARCHAR(50)   NOT NULL DEFAULT 'America/New_York',
  effective_from    DATE          NOT NULL DEFAULT CURRENT_DATE,
  effective_to      DATE,
  is_override       BOOLEAN       NOT NULL DEFAULT false,
  override_name     VARCHAR(100),

  -- Timestamps
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_business_hours_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_business_hours_tenant_id  ON public.business_hours (tenant_id);
CREATE INDEX idx_business_hours_day        ON public.business_hours (day_of_week);
CREATE INDEX idx_business_hours_override   ON public.business_hours (is_override);
CREATE INDEX idx_business_hours_effective  ON public.business_hours (effective_from, effective_to);

-- ============================================================================
-- TABLE: holiday_schedules — holiday closures
-- ============================================================================

CREATE TABLE public.holiday_schedules (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,

  -- Holiday info
  date              DATE          NOT NULL,
  name              VARCHAR(255)  NOT NULL,
  is_closed         BOOLEAN       NOT NULL DEFAULT true,

  -- Modified hours
  open_time         TIME,
  close_time        TIME,
  timezone          VARCHAR(50)   NOT NULL DEFAULT 'America/New_York',

  -- Recurrence
  is_recurring      BOOLEAN       NOT NULL DEFAULT true,

  -- Timestamps
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_holiday_schedules_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_holiday_schedules_tenant   ON public.holiday_schedules (tenant_id);
CREATE INDEX idx_holiday_schedules_date     ON public.holiday_schedules (date);
CREATE INDEX idx_holiday_schedules_recurring ON public.holiday_schedules (is_recurring);

-- ============================================================================
-- TABLE: caller_profiles — known caller CRM profiles
-- ============================================================================

CREATE TABLE public.caller_profiles (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Identity
  phone_number        VARCHAR(30)    NOT NULL,
  phone_hash          VARCHAR(64)    NOT NULL,

  -- Profile
  name                VARCHAR(255),
  email               VARCHAR(255),
  company             VARCHAR(255),
  notes               TEXT,
  tags_json           JSONB          NOT NULL DEFAULT '[]',

  -- AI-generated
  summary             TEXT,
  preferred_language  VARCHAR(10)    NOT NULL DEFAULT 'en',

  -- Stats
  total_calls         INT            NOT NULL DEFAULT 0,
  total_duration_sec  INT            NOT NULL DEFAULT 0,
  last_call_at        TIMESTAMPTZ,

  -- VIP / blocklist
  priority            VARCHAR(20)    NOT NULL DEFAULT 'normal',

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_caller_per_tenant UNIQUE (tenant_id, phone_hash),

  CONSTRAINT fk_caller_profiles_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT priority_range CHECK (
    priority IN ('blocked', 'low', 'normal', 'high', 'vip')
  )
);

CREATE INDEX idx_caller_profiles_tenant_id  ON public.caller_profiles (tenant_id);
CREATE INDEX idx_caller_profiles_phone_hash ON public.caller_profiles (phone_hash);
CREATE INDEX idx_caller_profiles_priority   ON public.caller_profiles (priority);
CREATE INDEX idx_caller_profiles_last_call  ON public.caller_profiles (last_call_at);

-- ============================================================================
-- TABLE: call_summaries — AI-generated call summaries
-- ============================================================================

CREATE TABLE public.call_summaries (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID          NOT NULL,
  call_id               UUID          NOT NULL,

  -- Summary content
  summary               TEXT,
  sentiment             VARCHAR(20),
  sentiment_score       NUMERIC(4,3),
  key_points_json       JSONB,
  action_items_json     JSONB,

  -- Caller intent
  primary_intent        VARCHAR(100),
  intents_detected_json JSONB,

  -- Quality
  call_quality_score    INT,

  -- Timestamps
  created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_call_summary_per_call UNIQUE (call_id),

  CONSTRAINT fk_call_summaries_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_call_summaries_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_call_summaries_tenant_id ON public.call_summaries (tenant_id);
CREATE INDEX idx_call_summaries_call_id   ON public.call_summaries (call_id);
CREATE INDEX idx_call_summaries_sentiment ON public.call_summaries (sentiment);

-- ============================================================================
-- TABLE: notification_logs — notification delivery tracking
-- ============================================================================

CREATE TABLE public.notification_logs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Notification details
  channel             public.notification_channel NOT NULL,
  recipient           VARCHAR(255)   NOT NULL,
  subject             VARCHAR(500),
  content             TEXT,
  content_html        TEXT,

  -- Context
  event_type          VARCHAR(100),
  entity_type         VARCHAR(50),
  entity_id           UUID,

  -- Status
  status              VARCHAR(20)    NOT NULL DEFAULT 'pending',
  error_message       TEXT,
  delivered_at        TIMESTAMPTZ,

  -- Provider metadata
  provider_message_id VARCHAR(255),
  metadata_json       JSONB          NOT NULL DEFAULT '{}',

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_notification_logs_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_notification_logs_tenant_id  ON public.notification_logs (tenant_id);
CREATE INDEX idx_notification_logs_channel    ON public.notification_logs (channel);
CREATE INDEX idx_notification_logs_status     ON public.notification_logs (status);
CREATE INDEX idx_notification_logs_event      ON public.notification_logs (event_type);
CREATE INDEX idx_notification_logs_entity     ON public.notification_logs (entity_type, entity_id);
CREATE INDEX idx_notification_logs_created    ON public.notification_logs (created_at);
CREATE INDEX idx_notification_logs_delivered  ON public.notification_logs (delivered_at);

-- ============================================================================
-- TABLE: integration_connections — third-party integrations
-- ============================================================================

CREATE TABLE public.integration_connections (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Provider
  provider            public.integration_provider NOT NULL,
  connection_name     VARCHAR(255)   NOT NULL DEFAULT 'Default',

  -- Configuration
  config_json         JSONB          NOT NULL DEFAULT '{}',

  -- Sync settings
  auto_sync           BOOLEAN        NOT NULL DEFAULT false,
  sync_frequency_min  INT            NOT NULL DEFAULT 15,

  -- Status
  status              VARCHAR(20)    NOT NULL DEFAULT 'pending',
  last_sync_at        TIMESTAMPTZ,
  error_message       TEXT,

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT uq_integration_per_tenant UNIQUE (tenant_id, provider),

  CONSTRAINT fk_integration_connections_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_integration_connections_tenant  ON public.integration_connections (tenant_id);
CREATE INDEX idx_integration_connections_provider ON public.integration_connections (provider);
CREATE INDEX idx_integration_connections_status   ON public.integration_connections (status);

-- ============================================================================
-- TABLE: oauth_tokens — encrypted OAuth 2.0 tokens
-- ============================================================================

CREATE TABLE public.oauth_tokens (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID           NOT NULL,

  -- Provider
  provider              public.integration_provider NOT NULL,
  provider_account_id   VARCHAR(255),

  -- Tokens (encrypted at app layer)
  access_token_enc      TEXT           NOT NULL,
  refresh_token_enc     TEXT,
  token_type            VARCHAR(20)    NOT NULL DEFAULT 'Bearer',

  -- Scopes & metadata
  scopes_json           JSONB          NOT NULL DEFAULT '[]',
  expires_at            TIMESTAMPTZ,

  -- Status
  is_active             BOOLEAN        NOT NULL DEFAULT true,
  last_used_at          TIMESTAMPTZ,

  -- Refresh tracking
  refresh_count         INT            NOT NULL DEFAULT 0,
  last_refresh_at       TIMESTAMPTZ,
  refresh_error         TEXT,

  -- Timestamps
  created_at            TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_oauth_tokens_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_oauth_tokens_tenant_id  ON public.oauth_tokens (tenant_id);
CREATE INDEX idx_oauth_tokens_provider   ON public.oauth_tokens (provider);
CREATE INDEX idx_oauth_tokens_is_active  ON public.oauth_tokens (is_active);

-- ============================================================================
-- TABLE: webhook_endpoints — outbound webhook endpoints
-- ============================================================================

CREATE TABLE public.webhook_endpoints (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Endpoint
  url                 VARCHAR(500)   NOT NULL,
  description         VARCHAR(255),

  -- Events
  events_json         JSONB          NOT NULL,

  -- Security
  secret              VARCHAR(255),
  headers_json        JSONB          NOT NULL DEFAULT '{}',

  -- Status
  is_active           BOOLEAN        NOT NULL DEFAULT true,

  -- Delivery stats
  success_count       INT            NOT NULL DEFAULT 0,
  failure_count       INT            NOT NULL DEFAULT 0,
  last_success_at     TIMESTAMPTZ,
  last_failure_at     TIMESTAMPTZ,
  last_error          TEXT,

  -- Timestamps
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_webhook_endpoints_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_webhook_endpoints_tenant_id ON public.webhook_endpoints (tenant_id);
CREATE INDEX idx_webhook_endpoints_is_active ON public.webhook_endpoints (is_active);

-- ============================================================================
-- TABLE: sync_logs — integration sync operation logs
-- ============================================================================

CREATE TABLE public.sync_logs (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID           NOT NULL,

  -- Operation
  provider            public.integration_provider NOT NULL,
  operation           VARCHAR(100)   NOT NULL,
  direction           VARCHAR(10)    NOT NULL,

  -- Status
  status              VARCHAR(20)    NOT NULL,

  -- Details
  records_processed   INT            NOT NULL DEFAULT 0,
  records_created     INT            NOT NULL DEFAULT 0,
  records_updated     INT            NOT NULL DEFAULT 0,
  records_failed      INT            NOT NULL DEFAULT 0,
  error_message       TEXT,
  details_json        JSONB          NOT NULL DEFAULT '{}',

  -- Timing
  started_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
  completed_at        TIMESTAMPTZ,
  duration_ms         INT,

  -- Timestamps (no updated_at — sync logs are immutable)
  created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

  CONSTRAINT fk_sync_logs_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_sync_logs_tenant_id  ON public.sync_logs (tenant_id);
CREATE INDEX idx_sync_logs_provider   ON public.sync_logs (provider);
CREATE INDEX idx_sync_logs_status     ON public.sync_logs (status);
CREATE INDEX idx_sync_logs_started_at ON public.sync_logs (started_at);
CREATE INDEX idx_sync_logs_created_at ON public.sync_logs (created_at);

-- ============================================================================
-- TABLE: usage_records — billable metering events
-- ============================================================================

CREATE TABLE public.usage_records (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID          NOT NULL,

  -- Event
  event_type        VARCHAR(50)   NOT NULL,
  event_subtype     VARCHAR(50),

  -- Reference
  call_id           UUID,
  resource_id       UUID,

  -- Quantity
  quantity          NUMERIC(12,4) NOT NULL,
  unit              VARCHAR(20)   NOT NULL,

  -- Cost
  cost_per_unit     NUMERIC(12,8) NOT NULL DEFAULT 0.0,
  total_cost        NUMERIC(12,6) NOT NULL DEFAULT 0.0,

  -- Time bucketing
  period_hour       TIMESTAMPTZ   NOT NULL,
  period_day        DATE          NOT NULL,
  period_month      VARCHAR(7)    NOT NULL,

  -- Timestamps (no updated_at — usage records are immutable)
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

  CONSTRAINT fk_usage_records_tenant
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_usage_records_call
    FOREIGN KEY (call_id) REFERENCES public.calls(id) ON DELETE SET NULL
);

CREATE INDEX idx_usage_records_tenant_id    ON public.usage_records (tenant_id);
CREATE INDEX idx_usage_records_event_type   ON public.usage_records (event_type);
CREATE INDEX idx_usage_records_call_id      ON public.usage_records (call_id);
CREATE INDEX idx_usage_records_period_day   ON public.usage_records (period_day);
CREATE INDEX idx_usage_records_period_month ON public.usage_records (period_month);
CREATE INDEX idx_usage_records_created_at   ON public.usage_records (created_at);
-- Composite index for billing aggregation queries
CREATE INDEX idx_usage_records_billing      ON public.usage_records (tenant_id, period_month, event_type);

-- ============================================================================
-- TABLE: audit_logs — immutable compliance audit trail
-- ============================================================================

CREATE TABLE public.audit_logs (
  id                BIGSERIAL     PRIMARY KEY,

  -- Tenant (no FK for write performance)
  tenant_id         UUID          NOT NULL,

  -- Actor
  actor_type        public.actor_type NOT NULL,
  actor_id          UUID,
  actor_email       VARCHAR(255),

  -- Action
  action            VARCHAR(100)  NOT NULL,
  resource_type     VARCHAR(50)   NOT NULL,
  resource_id       UUID,

  -- Details
  details_json      JSONB         NOT NULL DEFAULT '{}',
  ip_address        INET,
  user_agent        VARCHAR(500),

  -- Severity
  severity          VARCHAR(10)   NOT NULL DEFAULT 'info',

  -- Timestamps (immutable — never updated)
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_tenant_id   ON public.audit_logs (tenant_id);
CREATE INDEX idx_audit_logs_actor_type  ON public.audit_logs (actor_type);
CREATE INDEX idx_audit_logs_action      ON public.audit_logs (action);
CREATE INDEX idx_audit_logs_resource    ON public.audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at  ON public.audit_logs (created_at);
CREATE INDEX idx_audit_logs_severity    ON public.audit_logs (severity);
-- Composite for compliance queries
CREATE INDEX idx_audit_logs_tenant_time ON public.audit_logs (tenant_id, created_at DESC);

-- ============================================================================
-- TABLE: plan_definitions — subscription plan features (global)
-- ============================================================================

CREATE TABLE public.plan_definitions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity
  plan_tier             public.plan_tier NOT NULL UNIQUE,
  display_name          VARCHAR(100)   NOT NULL,
  description           TEXT,

  -- Limits
  max_minutes_monthly   INT            NOT NULL DEFAULT 100,
  max_concurrent_calls  INT            NOT NULL DEFAULT 1,
  max_users             INT            NOT NULL DEFAULT 1,
  max_phone_numbers     INT            NOT NULL DEFAULT 1,

  -- Features
  features_json         JSONB          NOT NULL DEFAULT '{}',

  -- Display
  is_public             BOOLEAN        NOT NULL DEFAULT true,
  sort_order            INT            NOT NULL DEFAULT 0,

  -- Timestamps
  created_at            TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ============================================================================
-- TRIGGERS: auto-set updated_at on tables with TimestampMixin
-- ============================================================================

CREATE TRIGGER trg_tenants_updated_at
  BEFORE UPDATE ON public.tenants
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tenant_configs_updated_at
  BEFORE UPDATE ON public.tenant_configs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_calls_updated_at
  BEFORE UPDATE ON public.calls
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_call_legs_updated_at
  BEFORE UPDATE ON public.call_legs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_recordings_updated_at
  BEFORE UPDATE ON public.recordings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_conversations_updated_at
  BEFORE UPDATE ON public.conversations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_prompts_updated_at
  BEFORE UPDATE ON public.prompts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_appointments_updated_at
  BEFORE UPDATE ON public.appointments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_routing_rules_updated_at
  BEFORE UPDATE ON public.routing_rules
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_faq_entries_updated_at
  BEFORE UPDATE ON public.faq_entries
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_business_hours_updated_at
  BEFORE UPDATE ON public.business_hours
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_holiday_schedules_updated_at
  BEFORE UPDATE ON public.holiday_schedules
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_caller_profiles_updated_at
  BEFORE UPDATE ON public.caller_profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_call_summaries_updated_at
  BEFORE UPDATE ON public.call_summaries
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_notification_logs_updated_at
  BEFORE UPDATE ON public.notification_logs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_integration_connections_updated_at
  BEFORE UPDATE ON public.integration_connections
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_oauth_tokens_updated_at
  BEFORE UPDATE ON public.oauth_tokens
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_webhook_endpoints_updated_at
  BEFORE UPDATE ON public.webhook_endpoints
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_plan_definitions_updated_at
  BEFORE UPDATE ON public.plan_definitions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================================
-- ROW-LEVEL SECURITY (RLS)
--
-- Supabase enables RLS by default. Policies enforce tenant_id isolation
-- so queries automatically scope data to the authenticated user's tenant.
--
-- Assumption: auth.uid() returns the Supabase Auth user UUID, and a
-- profiles or users table maps auth.uid() → tenant_id via a foreign key.
--
-- The policies below use a helper function that returns the current
-- user's tenant_id. You can also use a JWT claim (e.g. app.tenant_id).
-- ============================================================================

-- Helper: get current user's tenant_id
-- Adjust this function to match your auth schema (e.g. profiles table).

CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT tenant_id FROM public.users
  WHERE id = auth.uid()
  LIMIT 1;
$$;

-- ─── Enable RLS on all tables ───────────────────────────────────────────────

ALTER TABLE public.tenants                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_configs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calls                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_legs                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recordings               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tool_calls               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.routing_rules            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faq_entries              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_hours           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.holiday_schedules        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.caller_profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_summaries           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_logs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.integration_connections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oauth_tokens             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_endpoints        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_logs                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_records            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plan_definitions         ENABLE ROW LEVEL SECURITY;

-- ─── RLS Policies: tenant_isolation ─────────────────────────────────────────
--
-- Each policy allows authenticated users to read/write only rows where
-- tenant_id matches their own tenant. The tenats table and plan_definitions
-- use simpler policies since they are global or the user's own row.

CREATE POLICY "tenant_isolation" ON public.tenants
  FOR ALL
  USING (id = public.current_tenant_id())
  WITH CHECK (id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.tenant_configs
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.users
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.calls
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.call_legs
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.recordings
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.transcripts
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.conversations
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.messages
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.prompts
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.tool_calls
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.appointments
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.routing_rules
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.faq_entries
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.business_hours
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.holiday_schedules
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.caller_profiles
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.call_summaries
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.notification_logs
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.integration_connections
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.oauth_tokens
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.webhook_endpoints
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.sync_logs
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.usage_records
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE POLICY "tenant_isolation" ON public.audit_logs
  FOR ALL
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

-- plan_definitions is global (no tenant_id) — allow all authenticated reads
-- but restrict writes to service role only.

CREATE POLICY "plan_definitions_select" ON public.plan_definitions
  FOR SELECT
  TO authenticated
  USING (true);

-- ============================================================================
-- SUPABASE AUTH SCHEMA REFERENCE
-- ============================================================================
--
-- Supabase provides auth.* tables and the auth.uid() function.
-- The current_tenant_id() function above bridges auth.uid() to your
-- multi-tenant data via a profiles table.
--
-- Typical Supabase auth flow:
--   1. User signs up via Supabase Auth (auth.users)
--   2. A trigger on auth.users inserts into public.profiles
--   3. profiles.id = auth.uid(), profiles.tenant_id = tenant FK
--   4. RLS policies use current_tenant_id() to scope queries
--
-- Example profiles table (create if needed):
--
--   CREATE TABLE public.profiles (
--     id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
--     tenant_id  UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
--     email      VARCHAR(255),
--     created_at TIMESTAMPTZ DEFAULT now()
--   );
--   ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY "own_profile" ON public.profiles
--     FOR ALL USING (id = auth.uid());
--
-- ============================================================================

-- ============================================================================
-- SCHEMA COMPLETE
-- ============================================================================
--
-- Summary:
--   • 22 enum types
--   • 26 tables (tenants, tenant_configs, users, calls, call_legs, recordings,
--     transcripts, conversations, messages, prompts, tool_calls, appointments,
--     routing_rules, faq_entries, business_hours, holiday_schedules,
--     caller_profiles, call_summaries, notification_logs,
--     integration_connections, oauth_tokens, webhook_endpoints, sync_logs,
--     usage_records, audit_logs, plan_definitions)
--   • 50+ indexes for common query patterns
--   • 20 updated_at triggers
--   • 2 full-text search vector triggers (transcripts, faq_entries)
--   • RLS enabled on all 26 tables with tenant_isolation policies
--   • gen_random_uuid() for UUID generation
--   • Supabase auth schema reference and bridge pattern
-- ============================================================================
