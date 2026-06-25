// ───────────────────────────────────────────────────────────
// Authentication & User Types
// ───────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  avatarUrl: string | null;
  role: UserRole;
  isMfaEnabled: boolean;
  createdAt: string;
  lastLoginAt: string | null;
}

export type UserRole = "owner" | "admin" | "manager" | "viewer";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: PlanType;
  phoneNumber: string | null;
  timezone: string;
  businessName: string;
  industry: string | null;
  createdAt: string;
}

export type PlanType = "free" | "starter" | "growth" | "enterprise";

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignupData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  businessName: string;
  phoneNumber?: string;
}

export interface MfaSetup {
  secret: string;
  qrCodeUrl: string;
  backupCodes: string[];
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  newPassword: string;
}

export interface MagicLinkRequest {
  email: string;
}
