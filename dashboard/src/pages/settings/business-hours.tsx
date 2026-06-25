import { useState, useEffect } from "react";
import { useBusinessHours, useUpdateBusinessHours } from "@/hooks/use-business-hours";
import { BusinessHours } from "@/components/settings/BusinessHours";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Save } from "lucide-react";

const DEFAULT_HOURS = Array.from({ length: 7 }, (_, i) => ({
  dayOfWeek: i,
  isOpen: i > 0 && i < 6,
  openTime: "09:00",
  closeTime: "17:00",
  is24Hours: false,
}));

export default function BusinessHoursPage() {
  const { data: serverHours, isLoading, isError, refetch } = useBusinessHours();
  const updateHours = useUpdateBusinessHours();
  const [hours, setHours] = useState(DEFAULT_HOURS);

  useEffect(() => {
    if (serverHours) {
      setHours(Array.isArray(serverHours) ? serverHours : DEFAULT_HOURS);
    }
  }, [serverHours]);

  const handleSave = () => {
    updateHours.mutate(hours, {
      onSuccess: () => toast.success("Business hours saved"),
      onError: () => toast.error("Failed to save business hours"),
    });
  };

  if (isLoading) return <LoadingSpinner className="py-12" />;
  if (isError) return <ErrorState onRetry={refetch} />;

  return (
    <div className="space-y-6 max-w-3xl">
      <PageHeader title="Business Hours" description="Set your operating hours">
        <Button onClick={handleSave} disabled={updateHours.isPending}>
          <Save className="mr-1 h-4 w-4" /> {updateHours.isPending ? "Saving..." : "Save"}
        </Button>
      </PageHeader>
      <BusinessHours hours={hours} onChange={setHours} />
    </div>
  );
}
