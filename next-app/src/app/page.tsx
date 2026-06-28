import DashboardMockup from "@/components/DashboardMockup";
import HeroSection from "@/components/HeroSection";
import HonestMathSection from "@/components/HonestMathSection";
import HowItWorksSection from "@/components/HowItWorksSection";
import PricingSection from "@/components/PricingSection";
import ProofResultsSection from "@/components/ProofResultsSection";
import RoiCalculator from "@/components/RoiCalculator";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

export default function HomePage() {
  return (
    <div className="site">
      <SiteHeader />

      <main className="site-main">
        <HeroSection />
        <RoiCalculator />
        <ProofResultsSection />
        <HowItWorksSection />
        <DashboardMockup />
        <HonestMathSection />
        <PricingSection />
      </main>

      <SiteFooter />
    </div>
  );
}