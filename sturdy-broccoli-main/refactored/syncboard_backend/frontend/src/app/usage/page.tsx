'use client';

import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import UsageDashboard from '@/components/UsageDashboard';
import Link from 'next/link';

export default function UsagePage() {
  const { isAuthenticated, username } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-4">
              <Link href="/" className="text-xl font-bold text-blue-600">
                SyncBoard
              </Link>
              <span className="text-gray-300">|</span>
              <span className="text-gray-600">Usage & Billing</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
                Dashboard
              </Link>
              <Link href="/teams" className="text-gray-600 hover:text-gray-900">
                Teams
              </Link>
              <span className="text-gray-500">{username}</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Usage & Billing</h1>
          <p className="text-gray-500 mt-1">
            Monitor your usage and manage your subscription plan.
          </p>
        </div>

        <UsageDashboard />
      </div>
    </main>
  );
}
