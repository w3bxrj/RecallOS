import { useState, useEffect } from 'react';

export function useCountUp(target: number, durationMs = 600): number {
  const [count, setCount] = useState<number>(0);

  useEffect(() => {
    if (!Number.isFinite(target) || target <= 0) {
      setCount(target || 0);
      return;
    }

    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // easeOutCubic
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(target * ease));

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    const frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [target, durationMs]);

  return count;
}
