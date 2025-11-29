'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Link2, Github, Cloud, FileText, CheckCircle, XCircle, ExternalLink, Folder, File, Download, Loader2, ChevronRight, Home } from 'lucide-react';
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
  const [showGithubBrowser, setShowGithubBrowser] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<{ owner: string; repo: string } | null>(null);
  const [currentPath, setCurrentPath] = useState('');
  const [files, setFiles] = useState<any[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);

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
      if (service === 'github') {
        setShowGithubBrowser(false);
        setRepos([]);
        setSelectedRepo(null);
        setFiles([]);
      }
    } catch {
      toast.error('Failed to disconnect');
    }
  };

  const loadGithubRepos = async () => {
    setLoadingRepos(true);
    try {
      const data = await api.getGithubRepos();
      setRepos(data.repos || []);
      setShowGithubBrowser(true);
      if (data.repos.length > 0) {
        toast.success(`Found ${data.repos.length} repositories`);
      } else {
        toast('No repositories found', { icon: '📦' });
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to load GitHub repositories';
      toast.error(errorMsg);
    } finally {
      setLoadingRepos(false);
    }
  };

  const browseRepo = async (owner: string, repo: string, path: string = '') => {
    setLoadingFiles(true);
    setSelectedRepo({ owner, repo });
    setCurrentPath(path);
    try {
      const data = await api.getGithubRepoContents(owner, repo, path || undefined);
      setFiles(data.files || []);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to browse repository';
      toast.error(errorMsg);
    } finally {
      setLoadingFiles(false);
    }
  };

  const importFile = async (owner: string, repo: string, filePath: string) => {
    setImporting(filePath);
    try {
      const result = await api.importGithubFile(owner, repo, filePath);
      toast.success(`Imported ${filePath.split('/').pop()}!`);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to import file';
      toast.error(errorMsg);
    } finally {
      setImporting(null);
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
                    {integration.id === 'github' && (
                      <button
                        onClick={loadGithubRepos}
                        disabled={loadingRepos}
                        className="btn btn-primary text-sm flex items-center gap-2"
                      >
                        {loadingRepos ? <Loader2 className="w-4 h-4 animate-spin" /> : <Folder className="w-4 h-4" />}
                        Browse Repos
                      </button>
                    )}
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

      {/* GitHub Repository Browser */}
      {showGithubBrowser && statuses.github?.connected && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-xl font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Github className="w-6 h-6 text-primary" />
            GitHub Repository Browser
          </h2>

          {!selectedRepo ? (
            <div className="space-y-3">
              <p className="text-gray-400 text-sm mb-4">Select a repository to browse files</p>
              {repos.length > 0 ? (
                repos.map((repo) => (
                  <div
                    key={repo.name}
                    className="bg-dark-200 rounded-lg p-4 hover:bg-dark-300 transition-colors cursor-pointer"
                    onClick={() => browseRepo(repo.owner, repo.name)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-200">{repo.name}</h3>
                        <p className="text-sm text-gray-400 mt-1">{repo.description || 'No description'}</p>
                      </div>
                      {repo.stars !== undefined && (
                        <span className="text-sm text-yellow-400 flex items-center gap-1">
                          ⭐ {repo.stars}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-center text-gray-500 py-8">No repositories found</p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Breadcrumb */}
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <button
                  onClick={() => {
                    setSelectedRepo(null);
                    setFiles([]);
                    setCurrentPath('');
                  }}
                  className="hover:text-primary transition-colors flex items-center gap-1"
                >
                  <Home className="w-4 h-4" />
                  Repositories
                </button>
                <ChevronRight className="w-4 h-4" />
                <span className="text-gray-300">{selectedRepo.repo}</span>
                {currentPath && (
                  <>
                    <ChevronRight className="w-4 h-4" />
                    <span className="text-gray-300">{currentPath}</span>
                  </>
                )}
              </div>

              {/* File List */}
              {loadingFiles ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : files.length > 0 ? (
                <div className="space-y-2">
                  {/* Go up if in subdirectory */}
                  {currentPath && (
                    <div
                      className="bg-dark-200 rounded-lg p-3 hover:bg-dark-300 transition-colors cursor-pointer flex items-center gap-3"
                      onClick={() => {
                        const parentPath = currentPath.split('/').slice(0, -1).join('/');
                        browseRepo(selectedRepo.owner, selectedRepo.repo, parentPath);
                      }}
                    >
                      <Folder className="w-5 h-5 text-gray-400" />
                      <span className="text-gray-300">..</span>
                    </div>
                  )}

                  {files.map((file) => (
                    <div
                      key={file.path}
                      className="bg-dark-200 rounded-lg p-3 hover:bg-dark-300 transition-colors flex items-center justify-between group"
                    >
                      <div
                        className={`flex items-center gap-3 flex-1 ${file.type === 'dir' ? 'cursor-pointer' : ''}`}
                        onClick={() => {
                          if (file.type === 'dir') {
                            browseRepo(selectedRepo.owner, selectedRepo.repo, file.path);
                          }
                        }}
                      >
                        {file.type === 'dir' ? (
                          <Folder className="w-5 h-5 text-blue-400" />
                        ) : (
                          <File className="w-5 h-5 text-gray-400" />
                        )}
                        <span className="text-gray-300">{file.name}</span>
                        {file.size !== undefined && file.type === 'file' && (
                          <span className="text-xs text-gray-500">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        )}
                      </div>

                      {file.type === 'file' && (
                        <button
                          onClick={() => importFile(selectedRepo.owner, selectedRepo.repo, file.path)}
                          disabled={importing === file.path}
                          className="btn btn-primary btn-sm flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          {importing === file.path ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Download className="w-4 h-4" />
                          )}
                          Import
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-gray-500 py-8">Empty directory</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
