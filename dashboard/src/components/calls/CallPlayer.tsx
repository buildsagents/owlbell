import { useRef, useEffect, useState, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";
import { formatDuration } from "@/lib/utils";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Download,
} from "lucide-react";

interface CallPlayerProps {
  audioUrl: string;
  onTimeUpdate?: (time: number) => void;
}

export function CallPlayer({ audioUrl, onTimeUpdate }: CallPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [playbackRate, setPlaybackRate] = useState(1);

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#94a3b8",
      progressColor: "#0f172a",
      cursorColor: "#0f172a",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
    });

    ws.load(audioUrl);

    ws.on("ready", () => {
      setDuration(ws.getDuration());
    });

    ws.on("play", () => setIsPlaying(true));
    ws.on("pause", () => setIsPlaying(false));
    ws.on("audioprocess", (time: number) => {
      setCurrentTime(time);
      onTimeUpdate?.(time);
    });
    ws.on("seeking", (time: number) => {
      setCurrentTime(time);
      onTimeUpdate?.(time);
    });
    ws.on("finish", () => setIsPlaying(false));

    wavesurferRef.current = ws;

    return () => {
      ws.destroy();
    };
  }, [audioUrl, onTimeUpdate]);

  const togglePlay = useCallback(() => {
    wavesurferRef.current?.playPause();
  }, []);

  const skip = useCallback((seconds: number) => {
    if (!wavesurferRef.current) return;
    const newTime = Math.max(0, currentTime + seconds);
    wavesurferRef.current.setTime(newTime);
  }, [currentTime]);

  const toggleMute = useCallback(() => {
    if (!wavesurferRef.current) return;
    const newVolume = volume === 0 ? 1 : 0;
    wavesurferRef.current.setVolume(newVolume);
    setVolume(newVolume);
  }, [volume]);

  const changeSpeed = useCallback(() => {
    if (!wavesurferRef.current) return;
    const rates = [0.5, 1, 1.25, 1.5, 2];
    const next = rates[(rates.indexOf(playbackRate) + 1) % rates.length];
    wavesurferRef.current.setPlaybackRate(next);
    setPlaybackRate(next);
  }, [playbackRate]);

  return (
    <div className="rounded-lg border bg-card p-4">
      <div ref={containerRef} className="mb-3" />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button
            onClick={() => skip(-10)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          >
            <SkipBack className="h-4 w-4" />
          </button>
          <button
            onClick={togglePlay}
            className="rounded-full bg-primary p-2.5 text-primary-foreground hover:bg-primary/90"
          >
            {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button
            onClick={() => skip(10)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          >
            <SkipForward className="h-4 w-4" />
          </button>
        </div>

        <div className="text-sm text-muted-foreground tabular-nums">
          {formatDuration(Math.floor(currentTime))} / {formatDuration(Math.floor(duration))}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={toggleMute}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          >
            {volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
          <button
            onClick={changeSpeed}
            className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-accent tabular-nums"
          >
            {playbackRate}x
          </button>
          <a
            href={audioUrl}
            download
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          >
            <Download className="h-4 w-4" />
          </a>
        </div>
      </div>
    </div>
  );
}
