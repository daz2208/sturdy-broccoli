'use client';

import { useState, useEffect } from 'react';
import { Download, X } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export default function PWAInstallPrompt() {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

  useEffect(() => {
    // Check if running in standalone mode (already installed)
    const checkStandalone = () => {
      const standalone = window.matchMedia('(display-mode: standalone)').matches ||
        (window.navigator as any).standalone ||
        document.referrer.includes('android-app://');
      setIsStandalone(standalone);
    };

    checkStandalone();

    // Check if iOS
    const checkIOS = () => {
      const userAgent = window.navigator.userAgent.toLowerCase();
      setIsIOS(/iphone|ipad|ipod/.test(userAgent) && !(window as any).MSStream);
    };

    checkIOS();

    // Listen for the beforeinstallprompt event
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);

      // Show prompt after a delay (don't be too aggressive)
      const dismissed = localStorage.getItem('pwa-install-dismissed');
      const dismissedTime = dismissed ? parseInt(dismissed) : 0;
      const daysSinceDismissed = (Date.now() - dismissedTime) / (1000 * 60 * 60 * 24);

      // Only show if not dismissed in last 7 days
      if (daysSinceDismissed > 7) {
        setTimeout(() => setShowPrompt(true), 5000);
      }
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, []);

  const handleInstall = async () => {
    if (!installPrompt) return;

    // Show the install prompt
    await installPrompt.prompt();

    // Wait for the user to respond
    const { outcome } = await installPrompt.userChoice;

    if (outcome === 'accepted') {
      console.log('PWA installed');
    }

    // Clear the saved prompt
    setInstallPrompt(null);
    setShowPrompt(false);
  };

  const handleDismiss = () => {
    setShowPrompt(false);
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  };

  // Don't show if already installed
  if (isStandalone) return null;

  // iOS specific instructions
  if (isIOS && showPrompt) {
    return (
      <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-dark-100 border border-dark-300 rounded-xl p-4 shadow-lg z-50 animate-slideUp">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-primary" />
            <h3 className="font-semibold text-gray-200">Install SyncBoard</h3>
          </div>
          <button onClick={handleDismiss} className="text-gray-500 hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-gray-400 mb-3">
          Install SyncBoard on your device for quick access and offline support.
        </p>
        <div className="text-sm text-gray-300 space-y-2">
          <p>1. Tap the <span className="text-primary">Share</span> button in Safari</p>
          <p>2. Scroll and tap <span className="text-primary">&quot;Add to Home Screen&quot;</span></p>
          <p>3. Tap <span className="text-primary">Add</span></p>
        </div>
        <button onClick={handleDismiss} className="w-full mt-4 btn btn-secondary">
          Got it
        </button>
      </div>
    );
  }

  // Android/Desktop install prompt
  if (!showPrompt || !installPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-dark-100 border border-dark-300 rounded-xl p-4 shadow-lg z-50 animate-slideUp">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <Download className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-gray-200">Install SyncBoard</h3>
        </div>
        <button onClick={handleDismiss} className="text-gray-500 hover:text-gray-300">
          <X className="w-5 h-5" />
        </button>
      </div>
      <p className="text-sm text-gray-400 mb-4">
        Install SyncBoard on your device for quick access, offline support, and a better experience.
      </p>
      <div className="flex gap-2">
        <button onClick={handleInstall} className="flex-1 btn btn-primary flex items-center justify-center gap-2">
          <Download className="w-4 h-4" />
          Install
        </button>
        <button onClick={handleDismiss} className="btn btn-secondary">
          Not now
        </button>
      </div>
    </div>
  );
}
