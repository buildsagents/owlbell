import { describe, expect, it, beforeEach } from "vitest";
import {
  loadDemoScriptVersions,
  persistDemoScriptVersions,
} from "@/hooks/use-script-versions";

describe("useScriptVersions demo mode storage", () => {
  const key = "test-greeting";

  beforeEach(() => {
    localStorage.clear();
  });

  it("loadDemoScriptVersions returns empty when unset", () => {
    expect(loadDemoScriptVersions(key)).toEqual([]);
  });

  it("persistDemoScriptVersions round-trips versions", () => {
    const versions = [
      {
        id: "v1",
        label: "v1",
        content: "Thanks for calling",
        savedAt: "2026-06-29T00:00:00.000Z",
      },
    ];
    persistDemoScriptVersions(key, versions);
    expect(loadDemoScriptVersions(key)).toEqual(versions);
  });
});