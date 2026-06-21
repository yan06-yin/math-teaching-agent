"use client";

export function Skeleton({ className = "", width, height }: { className?: string; width?: number | string; height?: number | string }) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-200 ${className}`}
      style={{ width: width ?? "100%", height: height ?? "1rem" }}
    />
  );
}

export function TableSkeleton({ rows = 5, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2">
      {/* header */}
      <div className="flex gap-4 py-3 px-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="flex-1 h-5" />
        ))}
      </div>
      {/* rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 py-3 px-4 border-t border-gray-100">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="flex-1 h-4" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3">
      <Skeleton height={24} width="60%" />
      <Skeleton height={16} />
      <Skeleton height={16} width="40%" />
    </div>
  );
}
