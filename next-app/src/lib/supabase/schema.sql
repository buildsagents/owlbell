/**
 * Supabase database schema migration — run once on a fresh Supabase project.
 *
 * Run in the Supabase SQL editor or via the CLI:
 *   supabase db push
 *
 * RLS is enabled on all tables. Policies enforce org-scoped access via JWT claims.
 */

-- ============================================================
-- 1. Organizations (Tenants)
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  industry    TEXT,
  timezone    TEXT NOT NULL DEFAULT 'America/New_York',
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
  role        TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner','admin','viewer')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE USING (auth.uid() = id);

-- ============================================================
-- 3. Billing Subscriptions
-- ============================================================
CREATE TABLE IF NOT EXISTS subscriptions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE UNIQUE,
  stripe_customer_id       TEXT,
  stripe_subscription_id   TEXT,
  plan_tier                TEXT NOT NULL DEFAULT 'basic'
                             CHECK (plan_tier IN ('basic','pro','pro_plus','enterprise')),
  status                   TEXT NOT NULL DEFAULT 'trialing'
                             CHECK (status IN ('active','trialing','past_due','canceled','incomplete')),
  current_period_end       TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view own subscription"
  ON subscriptions FOR SELECT
  USING (org_id IN (
    SELECT org_id FROM profiles WHERE id = auth.uid()
  ));

-- ============================================================
-- 4. AI Voice Agents
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  voice_provider     TEXT NOT NULL DEFAULT 'retell' CHECK (voice_provider IN ('retell','vapi')),
  provider_agent_id  TEXT UNIQUE,
  phone_number       TEXT,
  system_prompt      TEXT,
  voice_id           TEXT,
  greeting           TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE agents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can manage own agents"
  ON agents FOR ALL
  USING (org_id IN (
    SELECT org_id FROM profiles WHERE id = auth.uid()
  ));

-- ============================================================
-- 5. Call Log Records
-- ============================================================
CREATE TABLE IF NOT EXISTS calls (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id          UUID REFERENCES agents(id) ON DELETE SET NULL,
  provider_call_id  TEXT UNIQUE,
  caller_number     TEXT,
  duration_seconds  INTEGER DEFAULT 0,
  status            TEXT NOT NULL DEFAULT 'completed'
                      CHECK (status IN ('completed','missed','in_progress','failed')),
  recording_url     TEXT,
  transcript        JSONB,
  summary           TEXT,
  action_items      JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view own calls"
  ON calls FOR SELECT
  USING (org_id IN (
    SELECT org_id FROM profiles WHERE id = auth.uid()
  ));

-- Voice platform webhook service role can insert calls
CREATE POLICY "Service role can insert calls"
  ON calls FOR INSERT
  WITH CHECK (true);

-- ============================================================
-- 6. Useful indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_calls_org_id     ON calls(org_id);
CREATE INDEX IF NOT EXISTS idx_calls_created_at ON calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agents_org_id    ON agents(org_id);
CREATE INDEX IF NOT EXISTS idx_profiles_org_id  ON profiles(org_id);

-- ============================================================
-- 7. Onboarding intake (post-checkout concierge portal)
--    Public can submit (customers aren't logged in at onboarding
--    time); reads are restricted to the service role / ops.
-- ============================================================
CREATE TABLE IF NOT EXISTS onboarding_intake (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email             TEXT NOT NULL,
  business_name     TEXT NOT NULL,
  stripe_session_id TEXT,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  status            TEXT NOT NULL DEFAULT 'submitted',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE onboarding_intake ENABLE ROW LEVEL SECURITY;

-- Anyone may submit their intake (they're not logged in yet at this point).
CREATE POLICY "Anyone can submit onboarding intake"
  ON onboarding_intake FOR INSERT
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_onboarding_intake_created_at ON onboarding_intake(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_onboarding_intake_email      ON onboarding_intake(email);
