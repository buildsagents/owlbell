import { useState } from "react";
import { useTeamMembers, useInviteMember } from "@/hooks/use-team";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { cn, formatRelative } from "@/lib/utils";
import type { TeamMember, TeamRole } from "@/types/team";
import { Users, UserPlus, Shield, User, Eye } from "lucide-react";

const roleConfig: Record<TeamRole, { label: string; icon: React.ComponentType<{className?: string}>; color: string }> = {
  owner: { label: "Owner", icon: Shield, color: "bg-purple-100 text-purple-700" },
  admin: { label: "Admin", icon: Shield, color: "bg-blue-100 text-blue-700" },
  manager: { label: "Manager", icon: User, color: "bg-emerald-100 text-emerald-700" },
  viewer: { label: "Viewer", icon: Eye, color: "bg-muted text-muted-foreground" },
};

export default function TeamPage() {
  const { data: members, isLoading } = useTeamMembers();
  const inviteMember = useInviteMember();
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TeamRole>("viewer");

  const handleInvite = () => {
    if (!inviteEmail) return;
    inviteMember.mutate({ email: inviteEmail, role: inviteRole }, {
      onSuccess: () => {
        setShowInvite(false);
        setInviteEmail("");
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Team" description="Manage team members and permissions">
        <Button onClick={() => setShowInvite(true)}>
          <UserPlus className="mr-1 h-4 w-4" /> Invite Member
        </Button>
      </PageHeader>

      <Dialog open={showInvite} onOpenChange={setShowInvite}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>Send an invitation email to join your team.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                placeholder="colleague@company.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Role</label>
              <div className="mt-1 flex gap-2">
                {(["admin", "manager", "viewer"] as TeamRole[]).map((role) => {
                  const config = roleConfig[role];
                  return (
                    <button
                      key={role}
                      onClick={() => setInviteRole(role)}
                      className={cn(
                        "rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
                        inviteRole === role ? "border-primary bg-primary text-primary-foreground" : "hover:bg-accent"
                      )}
                    >
                      {config.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button onClick={handleInvite} disabled={!inviteEmail || inviteMember.isPending} className="w-full">
              {inviteMember.isPending ? "Sending..." : "Send Invitation"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {isLoading ? <LoadingSpinner /> : members && members.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {members.map((member) => (
            <TeamMemberCard key={member.id} member={member} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="You're the only member"
          description="Invite your team to collaborate."
          icon={Users}
        >
          <Button onClick={() => setShowInvite(true)}>
            <UserPlus className="mr-1 h-4 w-4" /> Invite Member
          </Button>
        </EmptyState>
      )}
    </div>
  );
}

function TeamMemberCard({ member }: { member: TeamMember }) {
  const config = roleConfig[member.role];
  const RoleIcon = config.icon;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {member.firstName?.[0] || member.email[0]}
          </div>
          <div>
            <p className="font-medium">{member.firstName} {member.lastName}</p>
            <p className="text-xs text-muted-foreground">{member.email}</p>
          </div>
        </div>
        <Badge className={config.color}>
          <RoleIcon className="mr-1 h-3 w-3" /> {config.label}
        </Badge>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
        {member.lastActiveAt && <span>Active {formatRelative(member.lastActiveAt)}</span>}
        {member.joinedAt && <span>Joined {formatRelative(member.joinedAt)}</span>}
        {member.invitedAt && <span>Invited {formatRelative(member.invitedAt)}</span>}
      </div>
    </div>
  );
}
