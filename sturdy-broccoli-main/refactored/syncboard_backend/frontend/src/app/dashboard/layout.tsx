'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, checkAuth } = useAuthStore();

  useEffect(() => {
    // Only check auth after Zustand has rehydrated from localStorage
    if (hasHydrated) {
      checkAuth();
      if (!isAuthenticated) {
        router.push('/login');
      }
    }
  }, [isAuthenticated, hasHydrated, checkAuth, router]);

  // Show loading while Zustand rehydrates
  if (!hasHydrated) {
    return null;
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 ml-64 p-6 min-h-screen">
        {children}
      </main>
    </div>
  );
}
