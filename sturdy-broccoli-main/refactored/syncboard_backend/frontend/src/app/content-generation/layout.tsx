'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import Sidebar from '@/components/Sidebar';

export default function ContentGenerationLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, checkAuth, router]);

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
