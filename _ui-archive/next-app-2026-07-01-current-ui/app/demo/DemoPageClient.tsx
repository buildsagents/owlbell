"use client";

import { useSearchParams } from "next/navigation";
import DemoWebSandbox from "@/components/demo/DemoWebSandbox";

export default function DemoPageClient() {
  const params = useSearchParams();
  const vertical = params.get("vertical") || "plumbing";
  const businessName = params.get("business") || undefined;

  return <DemoWebSandbox vertical={vertical} businessName={businessName} />;
}