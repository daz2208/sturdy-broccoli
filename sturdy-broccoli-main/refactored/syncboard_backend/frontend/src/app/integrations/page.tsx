'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Link2, Github, Cloud, FileText, CheckCircle, XCircle, ExternalLink } from 'lucide-react';
import type { IntegrationStatus } from '@/types/api';

const INTEGRATIONS = [
  { id: 'github', name: 'GitHub', icon: Github, description: 'Import repositories and documentation' },
  { id: 'google', name: 'Google Drive', icon: Cloud, description: 'Sync documents from Google Drive' },
  { id: 'dropbox', name: 'Dropbox', icon: Cloud, description: 'Import files from Dropbox' },
  { id: 'notion', name: 'Notion', icon: FileText, description: 'Import Notion pages and databases' },
];

export default function IntegrationsPage() {
  const [statuses, setStatuses] = useState<Record<string, IntegrationStatus>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadStatuses(); }, []);

  const loadStatuses = async () => {
    try {
      const data = await api.getIntegrationStatus();
      setStatuses(data.integrations || {});
    } catch {
      toast.error('Failed to load integration statuses');
    } finally {
      setLoading(false);
    }
  };

  const connect = (service: string) => {
    window.location.href = api.getOAuthUrl(service);
  };

  const disconnect = async (service: string) => {
    try {
      await api.disconnectIntegration(service);
      toast.success(`Disconnected from ${service}`);
      loadStatuses();
    } catch {
      toast.error('Failed to disconnect');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Integrations</h1>
        <p className="text-gray-500">Connect external services to import documents</p>
      </div>

      <div className="grid gap-4">
        {INTEGRATIONS.map(integration => {
          const status = statuses[integration.id];
          const isConnected = status?.connected;
          const Icon = integration.icon;

          return (
            <div
              key={integration.id}
              className="bg-dark-100 rounded-xl border border-dark-300 p-6 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className="p-3 bg-dark-200 rounded-lg">
                  <Icon className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-200">{integration.name}</h3>
                  <p className="text-sm text-gray-500">{integration.description}</p>
                  {isConnected && status.user && (
                    <p className="text-xs text-gray-400 mt-1">Connected as {status.user}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3">
                {isConnected ? (
                  <>
                    <span className="flex items-center gap-1 text-green-400 text-sm">
                      <CheckCircle className="w-4 h-4" /> Connected
                    </span>
                    <button
                      onClick={() => disconnect(integration.id)}
                      className="btn btn-secondary text-sm"
                    >
                      Disconnect
                    </button>
                  </>
                ) : (
                  <>
                    <span className="flex items-center gap-1 text-gray-500 text-sm">
                      <XCircle className="w-4 h-4" /> Not connected
                    </span>
                    <button
                      onClick={() => connect(integration.id)}
                      className="btn btn-primary text-sm flex items-center gap-2"
                    >
                      <ExternalLink className="w-4 h-4" /> Connect
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
