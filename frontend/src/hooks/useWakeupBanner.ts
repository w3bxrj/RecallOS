import { useState, useEffect } from 'react';
import { subscribeToWakeup } from '../api/client';

export function useWakeupBanner(): boolean {
  const [isWaking, setIsWaking] = useState(false);

  useEffect(() => {
    const unsubscribe = subscribeToWakeup((waking) => {
      setIsWaking(waking);
    });
    return unsubscribe;
  }, []);

  return isWaking;
}
