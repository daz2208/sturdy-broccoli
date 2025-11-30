'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, checkAuth } = useAuthStore();

  useEffect(() => {
    if (hasHydrated) {
      checkAuth();
      if (isAuthenticated) {
        router.push('/dashboard');
      } else {
        router.push('/login');
      }
    }
  }, [isAuthenticated, hasHydrated, checkAuth, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}
