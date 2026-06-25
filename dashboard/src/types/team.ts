// ───────────────────────────────────────────────────────────
// Team Management Types
// ───────────────────────────────────────────────────────────

export type TeamRole = "owner" | "admin" | "manager" | "viewer";

export type TeamMemberStatus = "active" | "invited" | "inactive";

export interface TeamMember {
  id: string;
  tenantId: string;
  userId: string | null;
  email: string;
  firstName: string;
  lastName: string;
  role: TeamRole;
  status: TeamMemberStatus;
  avatarUrl: string | null;
  notificationsEnabled: boolean;
  lastActiveAt: string | null;
  invitedAt: string | null;
  joinedAt: string | null;
}

export interface TeamInvite {
  email: string;
  role: TeamRole;
}

export interface Permission {
  resource: string;
  action: string;
  allowed: boolean;
}

export const ROLE_PERMISSIONS: Record<TeamRole, Permission[]> = {
  owner: [{ resource: "*", action: "*", allowed: true }],
  admin: [
    { resource: "calls", action: "read", allowed: true },
    { resource: "calls", action: "update", allowed: true },
    { resource: "calls", action: "delete", allowed: true },
    { resource: "messages", action: "*", allowed: true },
    { resource: "appointments", action: "*", allowed: true },
    { resource: "analytics", action: "read", allowed: true },
    { resource: "settings", action: "*", allowed: true },
    { resource: "team", action: "read", allowed: true },
    { resource: "team", action: "invite", allowed: true },
    { resource: "team", action: "update", allowed: true },
    { resource: "billing", action: "read", allowed: true },
    { resource: "knowledge_base", action: "*", allowed: true },
    { resource: "integrations", action: "*", allowed: true },
  ],
  manager: [
    { resource: "calls", action: "read", allowed: true },
    { resource: "calls", action: "update", allowed: true },
    { resource: "messages", action: "*", allowed: true },
    { resource: "appointments", action: "*", allowed: true },
    { resource: "analytics", action: "read", allowed: true },
    { resource: "settings", action: "read", allowed: true },
    { resource: "settings", action: "update", allowed: true },
    { resource: "team", action: "read", allowed: true },
    { resource: "knowledge_base", action: "*", allowed: true },
  ],
  viewer: [
    { resource: "calls", action: "read", allowed: true },
    { resource: "messages", action: "read", allowed: true },
    { resource: "appointments", action: "read", allowed: true },
    { resource: "analytics", action: "read", allowed: true },
    { resource: "settings", action: "read", allowed: true },
  ],
};
