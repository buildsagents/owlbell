import { ROLE_PERMISSIONS } from "@/types/team";
import type { TeamRole } from "@/types/team";

export function hasPermission(
  role: TeamRole,
  resource: string,
  action: string
): boolean {
  if (role === "owner") return true;
  const permissions = ROLE_PERMISSIONS[role] || [];
  return permissions.some(
    (p) =>
      (p.resource === "*" || p.resource === resource) &&
      (p.action === "*" || p.action === action)
  );
}
