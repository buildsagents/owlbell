import { z } from "zod";

export const inviteMemberSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  role: z.enum(["admin", "manager", "viewer"], {
    required_error: "Please select a role",
  }),
});

export const updateRoleSchema = z.object({
  role: z.enum(["admin", "manager", "viewer"]),
});

export type InviteMemberInput = z.infer<typeof inviteMemberSchema>;
export type UpdateRoleInput = z.infer<typeof updateRoleSchema>;
