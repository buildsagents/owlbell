import DispatchBoard from "@/components/DispatchBoard";
import PhoneAlert from "@/components/PhoneAlert";

/** Hero visual stack - phone SMS + live dispatch board */
export default function HeroOpsVisual() {
  return (
    <div className="hero-ops-visual">
      <PhoneAlert />
      <DispatchBoard compact title="Tonight's overflow calls" subtitle="While your crew is on jobs" />
    </div>
  );
}