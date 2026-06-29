import { Slider } from "@/components/ui/slider";

type Props = {
  chunkSize: number;
  topK: number;
  onChunkSize: (v: number) => void;
  onTopK: (v: number) => void;
};

export function RagConfigPanel({ chunkSize, topK, onChunkSize, onTopK }: Props) {
  return (
    <div className="rounded-lg border p-4 space-y-4">
      <h3 className="text-sm font-semibold">RAG retrieval settings</h3>
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-2">
          <span>Chunk size (tokens)</span>
          <span>{chunkSize}</span>
        </div>
        <Slider
          value={[chunkSize]}
          min={256}
          max={2048}
          step={64}
          onValueChange={([v]) => onChunkSize(v)}
        />
      </div>
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-2">
          <span>Top-K passages</span>
          <span>{topK}</span>
        </div>
        <Slider value={[topK]} min={1} max={12} step={1} onValueChange={([v]) => onTopK(v)} />
      </div>
    </div>
  );
}