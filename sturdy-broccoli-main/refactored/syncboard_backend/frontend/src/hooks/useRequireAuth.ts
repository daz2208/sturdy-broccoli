import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

/**
 * Hook to protect pages requiring authentication.
 *
 * Waits for Zustand persist middleware to finish rehydrating from localStorage
 * before checking auth status. This prevents the "refresh kicks you to login" bug.
 *
 * @returns {boolean} True when auth is ready and user is authenticated
 *
 * @example
 * ```tsx
 * export default function ProtectedPage() {
 *   const isReady = useRequireAuth();
 *
 *   useEffect(() => {
 *     if (!isReady) return; // Wait for auth!
 *     loadData();
 *   }, [isReady]);
 *
 *   if (!isReady) {
 *     return <div>Loading...</div>;
 *   }
 *
 *   return <div>Protected content</div>;
 * }
 * ```
 */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const { isAuthenticated, hasHydrated } = useAuthStore();

  useEffect(() => {
    // Only redirect after hydration is complete
    if (hasHydrated && !isAuthenticated) {
      router.push('/login');
    }
  }, [hasHydrated, isAuthenticated, router]);

  // Return true only when:
  // 1. Zustand has finished rehydrating from localStorage
  // 2. User is authenticated
  return hasHydrated && isAuthenticated;
}
