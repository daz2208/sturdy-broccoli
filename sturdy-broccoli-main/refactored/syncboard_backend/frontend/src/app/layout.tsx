'use client';

import './globals.css';
import { Toaster } from 'react-hot-toast';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#2a2a2a',
              color: '#e0e0e0',
              border: '1px solid #333',
            },
          }}
        />
      </body>
    </html>
  );
}
