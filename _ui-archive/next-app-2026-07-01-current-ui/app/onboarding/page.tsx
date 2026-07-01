import OnboardingWizard from "@/components/onboarding/OnboardingWizard";

export const metadata = {
  title: "Set up your AI receptionist - Owlbell",
  description: "Get your plumbing business online with a Retell-powered receptionist through managed Owlbell setup.",
};

export default function OnboardingPage() {
  return (
    <main className="onboarding-page">
      <OnboardingWizard />
    </main>
  );
}
