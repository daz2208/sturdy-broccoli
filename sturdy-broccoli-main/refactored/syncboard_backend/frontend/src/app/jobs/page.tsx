'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Clock, CheckCircle, XCircle, Loader2, AlertCircle, Trash2 } from 'lucide-react';

interface Job {
  job_id: string;
  status: string;
  progress?: number;
  message?: string;
  current_step?: string;
  error?: string;
  document_id?: number;
  created_at?: string;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [notImplemented, setNotImplemented] = useState(false);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const response = await api.getJobs(20);
      setJobs(response.jobs || []);
      setNotImplemented(false);
    } catch (err: any) {
      // Handle 501 Not Implemented gracefully
      if (err.response?.status === 501) {
        setNotImplemented(true);
        setJobs([]);
      } else {
        toast.error('Failed to load jobs');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    if (!confirm('Cancel this job?')) return;

    try {
      await api.cancelJob(jobId);
      toast.success('Job cancelled');
      loadJobs();
    } catch (err) {
      toast.error('Failed to cancel job');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'FAILURE':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'PROCESSING':
      case 'PENDING':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      case 'REVOKED':
        return <XCircle className="w-5 h-5 text-gray-400" />;
      default:
        return <Clock className="w-5 h-5 text-yellow-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return 'text-green-400 bg-green-900/20';
      case 'FAILURE':
        return 'text-red-400 bg-red-900/20';
      case 'PROCESSING':
        return 'text-blue-400 bg-blue-900/20';
      case 'PENDING':
        return 'text-yellow-400 bg-yellow-900/20';
      case 'REVOKED':
        return 'text-gray-400 bg-gray-900/20';
      default:
        return 'text-gray-400 bg-gray-900/20';
    }
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (notImplemented) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Job Management</h1>
          <p className="text-gray-500">Monitor and manage background jobs</p>
        </div>

        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-3 mb-4">
            <AlertCircle className="w-6 h-6 text-yellow-400" />
            <h2 className="text-xl font-semibold text-gray-200">Feature Coming Soon</h2>
          </div>
          <div className="space-y-3 text-gray-400">
            <p>Job listing feature is currently being developed. Planned features include:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>View recent background jobs</li>
              <li>Track document processing status</li>
              <li>Monitor batch import progress</li>
              <li>Cancel running jobs</li>
            </ul>
            <p className="mt-4 text-sm">
              <strong className="text-gray-300">Current workaround:</strong> You can monitor document processing status
              from the Documents page or use the Admin panel&apos;s chunk status endpoint.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Job Management</h1>
          <p className="text-gray-500">Monitor and manage background jobs</p>
        </div>
        <button
          onClick={loadJobs}
          className="btn btn-secondary flex items-center gap-2"
        >
          <Loader2 className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-12 text-center">
          <Clock className="w-12 h-12 text-gray-500 mx-auto mb-4" />
          <p className="text-gray-400">No active jobs</p>
          <p className="text-gray-500 text-sm mt-2">Background jobs will appear here when documents are being processed</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div key={job.job_id} className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    {getStatusIcon(job.status)}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                        <span className="text-xs text-gray-500">Job ID: {job.job_id.slice(0, 8)}...</span>
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {job.progress !== undefined && job.status === 'PROCESSING' && (
                    <div className="mb-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">{job.current_step || 'Processing...'}</span>
                        <span className="text-gray-400">{job.progress}%</span>
                      </div>
                      <div className="w-full bg-dark-200 rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Message */}
                  {job.message && (
                    <p className="text-sm text-gray-400 mb-2">{job.message}</p>
                  )}

                  {/* Error */}
                  {job.error && (
                    <div className="bg-red-900/20 border border-red-700/50 rounded p-3 mb-2">
                      <p className="text-sm text-red-300">{job.error}</p>
                    </div>
                  )}

                  {/* Document Link */}
                  {job.document_id && job.status === 'SUCCESS' && (
                    <a
                      href={`/documents/${job.document_id}`}
                      className="text-sm text-primary hover:underline"
                    >
                      View document →
                    </a>
                  )}
                </div>

                {/* Cancel Button */}
                {(job.status === 'PROCESSING' || job.status === 'PENDING') && (
                  <button
                    onClick={() => handleCancelJob(job.job_id)}
                    className="p-2 bg-red-600 hover:bg-red-500 rounded text-white transition-colors"
                    title="Cancel job"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">About Background Jobs</h3>
        <p className="text-sm text-gray-400">
          Background jobs handle time-consuming tasks like document processing, OCR, and AI analysis.
          Jobs are processed by Celery workers in the background. You can cancel running jobs if needed.
        </p>
      </div>
    </div>
  );
}
