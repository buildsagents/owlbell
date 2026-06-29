import DashboardMockup from "@/components/DashboardMockup";
import HeroSection from "@/components/HeroSection";
import HonestMathSection from "@/components/HonestMathSection";
import HowItWorksSection from "@/components/HowItWorksSection";
import PricingSection from "@/components/PricingSection";
import ProofResultsSection from "@/components/ProofResultsSection";
import RoiCalculator from "@/components/RoiCalculator";
import SampleCallSection from "@/components/SampleCallSection";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import TrustBar from "@/components/marketing/TrustBar";
import LeadMagnetSection from "@/components/marketing/LeadMagnetSection";
import VerticalSelector from "@/components/marketing/VerticalSelector";
import StickyCtaBar from "@/components/marketing/StickyCtaBar";
import ExitIntentModal from "@/components/marketing/ExitIntentModal";

export default function HomePage() {
  return (
    <div className="site">
      <SiteHeader />

      <main className="site-main">
        <HeroSection />
        <TrustBar />
        <RoiCalculator />
        <VerticalSelector />
        <ProofResultsSection />
        <SampleCallSection />
        <HowItWorksSection />
        <LeadMagnetSection />
        <DashboardMockup />
        <HonestMathSection />
        <PricingSection />
      </main>

      <SiteFooter />
      <StickyCtaBar />
      <ExitIntentModal />
    </div>
  );
}