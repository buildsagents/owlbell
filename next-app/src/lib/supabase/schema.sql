/**
 * Owlbell Supabase schema - v2 (Retell-native, multi-tenant, UK plumbing focus)
 *
 * Run once on a fresh Supabase project via SQL editor or:
 *   supabase db push
 *
 * All tables have RLS. Policies enforce org-scoped access via JWT claims.
 */

-- ============================================================
-- 1. Organizations (Tenants)
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  industry    TEXT NOT NULL DEFAULT 'plumbing',
  timezone    TEXT NOT NULL DEFAULT 'Europe/London',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 2. User Profiles (linked to Supabase auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
  full_name   TEXT,
  email       TEXT,
  role        TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner','admin','viewer')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE USING (auth.uid() = id);

-- ============================================================
-- 3. Organization Settings
--    Stores business configuration set during onboarding
-- ============================================================
CREATE TABLE IF NOT EXISTS org_settings (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE UNIQUE,
  opening_hours         TEXT NOT NULL DEFAULT 'Mon-Fri 8:00-17:00',
  emergency_available   BOOLEAN NOT NULL DEFAULT true,
  service_areas         TEXT,
  services_offered      JSONB NOT NULL DEFAULT '[]'::jsonb,
  typical_pricing       TEXT,
  number_of_engineers   INTEGER NOT NULL DEFAULT 1,
  preferred_greeting    TEXT NOT NULL DEFAULT 'Thanks for calling {company}, this is {name}. Are you calling about an emergency or would you like to book a visit?',
  booking_rules         TEXT,
  emergency_routing     TEXT NOT NULL DEFAULT 'escalate_emergency',
  out_of_hours_behavior TEXT NOT NULL DEFAULT 'voicemail',
  transfer_numbers      JSONB NOT NULL DEFAULT '[]'::jsonb,
  voicemail_preferences TEXT,
  calendar_provider     TEXT CHECK (calendar_provider IN ('','google','microsoft')),
  appointment_duration  INTEGER NOT NULL DEFAULT 60,
  buffer_time           INTEGER NOT NULL DEFAULT 15,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE org_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage settings"
  ON org_settings FOR ALL
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- ============================================================
-- 4. AI Voice Agents (Retell-only)
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  voice_provider     TEXT NOT NULL DEFAULT 'retell' CHECK (voice_provider = 'retell'),
  provider_agent_id  TEXT UNIQUE,
  phone_number       TEXT,
  system_prompt      TEXT,
  voice_id           TEXT,
  voice_name         TEXT,
  greeting           TEXT,
  status             TEXT NOT NULL DEFAULT 'provisioning'
                       CHECK (status IN ('provisioning','active','paused','error')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage own agents"
  ON agents FOR ALL
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- ============================================================
-- 5. Phone Numbers
-- ============================================================
CREATE TABLE IF NOT EXISTS phone_numbers (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id          UUID REFERENCES agents(id) ON DELETE SET NULL,
  number            TEXT NOT NULL,
  provider          TEXT NOT NULL DEFAULT 'retell' CHECK (provider = 'retell'),
  type              TEXT NOT NULL DEFAULT 'new' CHECK (type IN ('new','port')),
  status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','active','porting','error','released')),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, number)
);
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage phone numbers"
  ON phone_numbers FOR ALL
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- ============================================================
-- 6. Call Log Records
-- ============================================================
CREATE TABLE IF NOT EXISTS calls (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id          UUID REFERENCES agents(id) ON DELETE SET NULL,
  provider_call_id  TEXT UNIQUE,
  caller_number     TEXT,
  caller_name       TEXT,
  duration_seconds  INTEGER DEFAULT 0,
  status            TEXT NOT NULL DEFAULT 'completed'
                      CHECK (status IN ('completed','missed','in_progress','failed')),
  recording_url     TEXT,
  transcript        JSONB,
  summary           TEXT,
  action_items      JSONB,
  is_emergency      BOOLEAN NOT NULL DEFAULT false,
  appointment_id    UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view own calls"
  ON calls FOR SELECT
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- Service role can insert calls from Retell webhooks
CREATE POLICY "Service role can insert calls"
  ON calls FOR INSERT
  WITH CHECK (true);

-- ============================================================
-- 7. Appointments (booked via AI)
-- ============================================================
CREATE TABLE IF NOT EXISTS appointments (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  call_id           UUID REFERENCES calls(id) ON DELETE SET NULL,
  caller_name       TEXT,
  caller_number     TEXT,
  caller_address    TEXT,
  scheduled_at      TIMESTAMPTZ NOT NULL,
  duration_minutes  INTEGER NOT NULL DEFAULT 60,
  description       TEXT,
  status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','confirmed','completed','cancelled')),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage appointments"
  ON appointments FOR ALL
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- ============================================================
-- 8. Knowledge Base Entries
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_bases (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  type              TEXT NOT NULL CHECK (type IN ('faq','price_list','service_info','policy','website_import')),
  title             TEXT,
  content           TEXT NOT NULL,
  source_url        TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage knowledge base"
  ON knowledge_bases FOR ALL
  USING (org_id IN (SELECT org_id FROM profiles WHERE id = auth.uid()));

-- ============================================================
-- 9. Onboarding Intake (pre-auth submission)
--    Public can submit; reads restricted to service role.
-- ============================================================
CREATE TABLE IF NOT EXISTS onboarding_intake (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email             TEXT NOT NULL,
  business_name     TEXT NOT NULL,
  owner_name        TEXT,
  mobile            TEXT,
  stripe_session_id TEXT,
  org_id            UUID REFERENCES organizations(id) ON DELETE SET NULL,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  status            TEXT NOT NULL DEFAULT 'submitted'
                      CHECK (status IN ('submitted','provisioning','completed','failed')),
  error_message     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at      TIMESTAMPTZ
);
ALTER TABLE onboarding_intake ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can submit onboarding intake"
  ON onboarding_intake FOR INSERT
  WITH CHECK (true);

-- ============================================================
-- 10. Useful Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_calls_org_id          ON calls(org_id);
CREATE INDEX IF NOT EXISTS idx_calls_created_at      ON calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_is_emergency    ON calls(org_id, is_emergency) WHERE is_emergency = true;
CREATE INDEX IF NOT EXISTS idx_agents_org_id         ON agents(org_id);
CREATE INDEX IF NOT EXISTS idx_profiles_org_id       ON profiles(org_id);
CREATE INDEX IF NOT EXISTS idx_appointments_org_id   ON appointments(org_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON appointments(org_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_kb_org_id             ON knowledge_bases(org_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_org_id  ON phone_numbers(org_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_intake_email ON onboarding_intake(email);
