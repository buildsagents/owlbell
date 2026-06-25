import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useResetPassword } from "@/hooks/use-forgot-password";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PhoneCall, Loader2 } from "lucide-react";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const resetPassword = useResetPassword();

  const token = searchParams.get("token") || "";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!token) {
      setError("Invalid or missing reset token");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    resetPassword.mutate({ token, password }, {
      onSuccess: () => setDone(true),
      onError: () => {
        setError("Failed to reset password");
      },
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 p-4 dark:from-slate-900 dark:to-slate-800">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <PhoneCall className="h-5 w-5" />
          </div>
          <span className="text-2xl font-bold">Owlbell</span>
        </div>
        <Card>
          <CardHeader><CardTitle>Reset Password</CardTitle></CardHeader>
          <CardContent>
            {done ? (
              <div className="text-center py-4">
                <p className="text-emerald-600 font-medium">Password reset successfully!</p>
                <Link to="/login" className="mt-2 text-sm text-primary hover:underline">Sign in</Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">New Password</label>
                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                </div>
                {error && <p className="text-sm text-rose-500">{error}</p>}
                <Button type="submit" className="w-full" disabled={resetPassword.isPending}>
                  {resetPassword.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Reset Password
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
