interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export default function Skeleton({ className = "", style }: SkeletonProps) {
  return (
    <div
      className={className}
      style={{
        background: "var(--gray-200)",
        borderRadius: "var(--radius-sm)",
        animation: "pulse 2s var(--ease-in-out) infinite",
        ...style,
      }}
      aria-hidden="true"
    />
  );
}
