'use client';

import { WifiOff, RefreshCw } from 'lucide-react';

export default function OfflinePage() {
  const handleRetry = () => {
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-dark flex items-center justify-center p-4">
      <div className="text-center max-w-md">
        <div className="bg-dark-100 rounded-full p-6 inline-block mb-6">
          <WifiOff className="w-12 h-12 text-gray-500" />
        </div>

        <h1 className="text-2xl font-bold text-gray-200 mb-4">
          You&apos;re Offline
        </h1>

        <p className="text-gray-400 mb-6">
          It looks like you&apos;ve lost your internet connection. Some features may not be available until you&apos;re back online.
        </p>

        <div className="space-y-4">
          <button
            onClick={handleRetry}
            className="w-full btn btn-primary flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>

          <div className="text-sm text-gray-500">
            <p>You can still:</p>
            <ul className="mt-2 space-y-1">
              <li>• View cached documents</li>
              <li>• Browse your knowledge base</li>
              <li>• Access recent searches</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
