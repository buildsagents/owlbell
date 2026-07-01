import { describe, expect, it } from "vitest";
import { parseCallWebhook } from "./voice-service";

function mockRetellPayload(overrides = {}) {
  return {
    call_id: "call-retell-123",
    caller_number: "+447700900000",
    start_timestamp: 1717000000000,
    end_timestamp: 1717000060000,
    duration_ms: 60000,
    call_result: "completed",
    recording_url: "https://api.retellai.com/recording.mp3",
    transcript: [
      { role: "agent", content: "Hello. How can I help?" },
      { role: "user", content: "I have a burst pipe" },
      { role: "agent", content: "I will flag this as an emergency." },
    ],
    summary: {
      summary: "Customer called about a burst pipe. Flagged as emergency.",
      is_emergency: true,
      appointment_booked: false,
      caller_name: "John Smith",
      caller_phone: "+447700900000",
      caller_address: "123 High Street, London",
    },
    ...overrides,
  };
}

describe("parseCallWebhook", () => {
  it("parses a standard completed call", () => {
    const result = parseCallWebhook(mockRetellPayload());

    expect(result.provider_call_id).toBe("call-retell-123");
    expect(result.caller_number).toBe("+447700900000");
    expect(result.duration_seconds).toBe(60);
    expect(result.status).toBe("completed");
    expect(result.recording_url).toBe("https://api.retellai.com/recording.mp3");
  });

  it("flags emergency calls from analysis", () => {
    const result = parseCallWebhook(mockRetellPayload());
    expect(result.action_items?.is_emergency).toBe(true);
    expect(result.action_items?.appointment_booked).toBe(false);
  });

  it("flags emergency from transcript keywords", () => {
    const payload = mockRetellPayload({
      summary: { is_emergency: false, appointment_booked: false },
    });
    const result = parseCallWebhook(payload);
    expect(result.action_items?.is_emergency).toBe(true);
  });

  it("flags appointment from analysis", () => {
    const payload = mockRetellPayload({
      summary: { is_emergency: false, appointment_booked: true },
    });
    const result = parseCallWebhook(payload);
    expect(result.action_items?.appointment_booked).toBe(true);
  });

  it("flags appointment from transcript keywords", () => {
    const payload = mockRetellPayload({
      transcript: [
        { role: "agent", content: "I have scheduled you for Tuesday at 10am." },
      ],
      summary: { is_emergency: false, appointment_booked: false },
    });
    const result = parseCallWebhook(payload);
    expect(result.action_items?.appointment_booked).toBe(true);
  });

  it("extracts caller details from analysis", () => {
    const result = parseCallWebhook(mockRetellPayload());
    expect(result.action_items?.caller_name).toBe("John Smith");
    expect(result.action_items?.caller_phone).toBe("+447700900000");
    expect(result.action_items?.caller_address).toBe("123 High Street, London");
  });

  it("handles missed calls", () => {
    const payload = mockRetellPayload({
      call_id: "call-missed",
      start_timestamp: 1717000000000,
      end_timestamp: 1717000000000,
      duration_ms: 0,
      call_result: "no_answer",
      transcript: [],
      summary: {},
    });
    const result = parseCallWebhook(payload);
    expect(result.status).toBe("failed");
    expect(result.duration_seconds).toBe(0);
  });

  it("handles string transcript format", () => {
    const payload = mockRetellPayload({
      transcript: "Agent: Hello\nUser: I need a tap repaired",
      summary: {},
    });
    const result = parseCallWebhook(payload);
    expect(result.transcript).toEqual([
      { role: "agent", content: "Hello" },
      { role: "user", content: "I need a tap repaired" },
    ]);
  });

  it("handles missing analysis gracefully", () => {
    const payload = mockRetellPayload({
      transcript: [
        { role: "agent", content: "Hello. How can I help?" },
        { role: "user", content: "I need a tap repaired" },
      ],
    });
    delete (payload as { summary?: unknown }).summary;
    const result = parseCallWebhook(payload);
    expect(result.summary).toBeNull();
    expect(result.action_items?.is_emergency).toBe(false);
    expect(result.action_items?.appointment_booked).toBe(false);
    expect(result.action_items?.caller_name).toBeUndefined();
  });
});
