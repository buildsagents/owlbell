import { create } from "zustand";
import type { ActiveCall, CallFilters, TranscriptSegment } from "@/types/call";

interface CallState {
  activeCalls: ActiveCall[];
  selectedCallId: string | null;
  filters: CallFilters;
  isDetailPanelOpen: boolean;
  isTranscriptPlaying: boolean;
  transcriptPlaybackTime: number;

  setActiveCalls: (calls: ActiveCall[]) => void;
  addActiveCall: (call: ActiveCall) => void;
  updateActiveCall: (callId: string, updates: Partial<ActiveCall>) => void;
  removeActiveCall: (callId: string) => void;
  appendTranscriptSegment: (callId: string, segment: TranscriptSegment) => void;
  setSelectedCallId: (callId: string | null) => void;
  setFilters: (filters: Partial<CallFilters>) => void;
  resetFilters: () => void;
  setDetailPanelOpen: (open: boolean) => void;
  setTranscriptPlaying: (playing: boolean) => void;
  setTranscriptPlaybackTime: (time: number) => void;
}

const defaultFilters: CallFilters = {
  status: null,
  direction: null,
  outcome: null,
  dateFrom: null,
  dateTo: null,
  callerNumber: null,
  search: null,
  tags: [],
};

export const useCallStore = create<CallState>()((set) => ({
  activeCalls: [],
  selectedCallId: null,
  filters: { ...defaultFilters },
  isDetailPanelOpen: false,
  isTranscriptPlaying: false,
  transcriptPlaybackTime: 0,

  setActiveCalls: (calls) => set({ activeCalls: calls }),
  addActiveCall: (call) =>
    set((state) => ({
      activeCalls: [...state.activeCalls.filter((c) => c.id !== call.id), call],
    })),
  updateActiveCall: (callId, updates) =>
    set((state) => ({
      activeCalls: state.activeCalls.map((c) =>
        c.id === callId ? { ...c, ...updates } : c
      ),
    })),
  removeActiveCall: (callId) =>
    set((state) => ({
      activeCalls: state.activeCalls.filter((c) => c.id !== callId),
    })),
  appendTranscriptSegment: (callId, segment) =>
    set((state) => ({
      activeCalls: state.activeCalls.map((c) =>
        c.id === callId
          ? { ...c, currentTranscript: [...(c.currentTranscript || []), segment] }
          : c
      ),
    })),
  setSelectedCallId: (callId) => set({ selectedCallId: callId }),
  setFilters: (filters) =>
    set((state) => ({ filters: { ...state.filters, ...filters } })),
  resetFilters: () => set({ filters: { ...defaultFilters } }),
  setDetailPanelOpen: (open) => set({ isDetailPanelOpen: open }),
  setTranscriptPlaying: (playing) => set({ isTranscriptPlaying: playing }),
  setTranscriptPlaybackTime: (time) => set({ transcriptPlaybackTime: time }),
}));
