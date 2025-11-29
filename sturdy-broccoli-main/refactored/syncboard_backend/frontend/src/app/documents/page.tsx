'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { FileText, Upload, Trash2, ExternalLink, Filter, Image, Link, Type, Wifi, Loader2, CheckCircle, XCircle, Download } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import type { Document } from '@/types/api';
import { useWebSocket } from '@/hooks/useWebSocket';

// Type for tracking upload jobs
interface UploadJob {
  id: string;
  filename: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
  progress: number;
  message?: string;
  error?: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadMode, setUploadMode] = useState<'file' | 'url' | 'text' | 'image'>('file');
  const [textContent, setTextContent] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [filter, setFilter] = useState({ source_type: '', skill_level: '' });

  // Upload jobs tracking
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const pollIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // WebSocket for real-time document updates
  const { isConnected, on } = useWebSocket();

  useEffect(() => {
    loadDocuments();

    // Listen for real-time document events
    const unsubCreated = on('document_created', () => {
      loadDocuments(); // Refresh list when new document created
    });

    const unsubDeleted = on('document_deleted', () => {
      loadDocuments(); // Refresh list when document deleted
    });

    const unsubUpdated = on('document_updated', () => {
      loadDocuments(); // Refresh list when document updated
    });

    // Listen for job completion events
    const unsubJobCompleted = on('job_completed', (event) => {
      const jobId = event.data.job_id as string;
      if (jobId) {
        setUploadJobs(prev => prev.map(job =>
          job.id === jobId ? { ...job, status: 'success', progress: 100, message: 'Completed!' } : job
        ));
        loadDocuments();
      }
    });

    const unsubJobFailed = on('job_failed', (event) => {
      const jobId = event.data.job_id as string;
      if (jobId) {
        setUploadJobs(prev => prev.map(job =>
          job.id === jobId ? { ...job, status: 'failed', error: event.data.error as string } : job
        ));
      }
    });

    return () => {
      unsubCreated();
      unsubDeleted();
      unsubUpdated();
      unsubJobCompleted();
      unsubJobFailed();
      // Clean up all polling intervals
      pollIntervalsRef.current.forEach(interval => clearInterval(interval));
    };
  }, [on]);

  // Clean up completed jobs after 5 seconds
  useEffect(() => {
    const completedJobs = uploadJobs.filter(j => j.status === 'success' || j.status === 'failed');
    if (completedJobs.length > 0) {
      const timeout = setTimeout(() => {
        setUploadJobs(prev => prev.filter(j => j.status !== 'success' && j.status !== 'failed'));
      }, 5000);
      return () => clearTimeout(timeout);
    }
  }, [uploadJobs]);

  const loadDocuments = async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data.documents);
    } catch (err) {
      toast.error('Failed to load documents');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Poll job status
  const pollJobStatus = useCallback(async (jobId: string) => {
    try {
      const status = await api.getJobStatus(jobId);

      setUploadJobs(prev => prev.map(job => {
        if (job.id !== jobId) return job;

        if (status.status === 'SUCCESS') {
          // Stop polling
          const interval = pollIntervalsRef.current.get(jobId);
          if (interval) {
            clearInterval(interval);
            pollIntervalsRef.current.delete(jobId);
          }
          loadDocuments(); // Refresh documents list
          return { ...job, status: 'success', progress: 100, message: 'Completed!' };
        }

        if (status.status === 'FAILURE') {
          // Stop polling
          const interval = pollIntervalsRef.current.get(jobId);
          if (interval) {
            clearInterval(interval);
            pollIntervalsRef.current.delete(jobId);
          }
          return { ...job, status: 'failed', error: status.error || 'Upload failed' };
        }

        // Still processing
        return {
          ...job,
          status: 'processing',
          progress: status.progress || 50,
          message: status.message || status.current_step || 'Processing...'
        };
      }));
    } catch (err) {
      console.error(`Failed to poll job ${jobId}:`, err);
    }
  }, []);

  // Start polling for a job
  const startJobPolling = useCallback((jobId: string, filename: string) => {
    // Add job to tracking
    setUploadJobs(prev => [...prev, {
      id: jobId,
      filename,
      status: 'pending',
      progress: 0,
      message: 'Queued for processing...'
    }]);

    // Start polling every 2 seconds
    const interval = setInterval(() => pollJobStatus(jobId), 2000);
    pollIntervalsRef.current.set(jobId, interval);

    // Initial poll
    pollJobStatus(jobId);
  }, [pollJobStatus]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);

    for (const file of acceptedFiles) {
      try {
        const base64 = await fileToBase64(file);
        const response = await api.uploadFile(base64, file.name);

        // Start polling for this job
        if (response.job_id) {
          startJobPolling(response.job_id, file.name);
          toast.success(`Queued: ${file.name}`);
        }
      } catch (err) {
        console.error(`Failed to upload ${file.name}:`, err);
        toast.error(`Failed to queue: ${file.name}`);
      }
    }

    setUploading(false);
  }, [startJobPolling]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      // Documents
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt', '.md', '.rst', '.tex'],
      'text/csv': ['.csv'],
      // Spreadsheets
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      // Presentations
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      // Audio (transcription)
      'audio/*': ['.mp3', '.wav', '.m4a', '.ogg', '.flac'],
      // Notebooks & Data
      'application/json': ['.json', '.ipynb'],
      'application/x-yaml': ['.yaml', '.yml'],
      'text/xml': ['.xml'],
      'application/toml': ['.toml'],
      // Code files
      'text/x-python': ['.py'],
      'text/javascript': ['.js', '.jsx'],
      'text/typescript': ['.ts', '.tsx'],
      'text/x-java': ['.java'],
      'text/x-c': ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'],
      'text/x-go': ['.go'],
      'text/x-rust': ['.rs'],
      'text/x-ruby': ['.rb'],
      'text/x-php': ['.php'],
      'text/x-swift': ['.swift'],
      'text/x-kotlin': ['.kt'],
      'text/x-scala': ['.scala'],
      'text/x-r': ['.r'],
      'text/html': ['.html', '.vue'],
      'text/css': ['.css', '.scss', '.sass'],
      'text/x-sh': ['.sh', '.bash', '.zsh', '.fish'],
      'text/x-powershell': ['.ps1'],
      'text/x-sql': ['.sql'],
      'text/x-ini': ['.ini', '.conf'],
      // Archives & Books
      'application/zip': ['.zip'],
      'application/epub+zip': ['.epub'],
      // Subtitles
      'text/vtt': ['.vtt', '.srt'],
    },
  });

  // Image upload dropzone (separate for OCR)
  const onDropImage = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);

    for (const file of acceptedFiles) {
      try {
        const base64 = await fileToBase64(file);
        const response = await api.uploadImage(base64, file.name);

        // Start polling for this job
        if (response.job_id) {
          startJobPolling(response.job_id, file.name);
          toast.success(`Queued for OCR: ${file.name}`);
        }
      } catch (err) {
        console.error(`Failed to upload image ${file.name}:`, err);
        toast.error(`Failed to queue: ${file.name}`);
      }
    }

    setUploading(false);
  }, [startJobPolling]);

  const { getRootProps: getImageRootProps, getInputProps: getImageInputProps, isDragActive: isImageDragActive } = useDropzone({
    onDrop: onDropImage,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'],
    },
  });

  const uploadText = async () => {
    if (!textContent.trim()) {
      toast.error('Please enter some content');
      return;
    }
    setUploading(true);
    try {
      const response = await api.uploadText(textContent);
      // Text upload is synchronous, so we just refresh
      toast.success('Text uploaded successfully');
      setTextContent('');
      loadDocuments();
    } catch (err) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const uploadUrl = async () => {
    if (!urlInput.trim()) {
      toast.error('Please enter a URL');
      return;
    }
    setUploading(true);
    try {
      const response = await api.uploadUrl(urlInput);

      // Start polling for this job
      if (response.job_id) {
        startJobPolling(response.job_id, urlInput.substring(0, 50));
        toast.success('URL queued for processing');
      }
      setUrlInput('');
    } catch (err) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const deleteDocument = async (docId: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await api.deleteDocument(docId);
      toast.success('Document deleted');
      setDocuments(docs => docs.filter(d => d.id !== docId));
    } catch (err) {
      toast.error('Failed to delete document');
    }
  };

  const downloadDocument = async (docId: number, title: string) => {
    console.log('Download button clicked:', { docId, title });
    try {
      console.log('Calling api.downloadDocument...');
      await api.downloadDocument(docId, title);
      console.log('Download completed successfully');
      toast.success('Download started');
    } catch (err: any) {
      console.error('Download error:', err);
      console.error('Error details:', err?.response?.data || err?.message);
      toast.error(`Download failed: ${err?.response?.data?.detail || err?.message || 'Unknown error'}`);
    }
  };

  const exportAll = async (format: 'json' | 'markdown') => {
    try {
      const blob = await api.exportAll(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `knowledge-base-export.${format === 'json' ? 'json' : 'md'}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Export downloaded');
    } catch (err) {
      toast.error('Export failed');
      console.error('Export error:', err);
    }
  };

  const filteredDocs = documents.filter(doc => {
    if (filter.source_type && doc.source_type !== filter.source_type) return false;
    if (filter.skill_level && doc.skill_level !== filter.skill_level) return false;
    return true;
  });

  const sourceTypes = [...new Set(documents.map(d => d.source_type))];
  const skillLevels = [...new Set(documents.map(d => d.skill_level).filter(Boolean))];

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100">Documents</h1>
            {isConnected && (
              <span className="flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-1 rounded">
                <Wifi className="w-3 h-3" />
                Live
              </span>
            )}
          </div>
          <p className="text-gray-500">{documents.length} documents in your knowledge base</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportAll('json')}
            className="btn btn-secondary flex items-center gap-2"
            title="Export all documents as JSON"
          >
            <Download className="w-4 h-4" />
            Export All
          </button>
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Upload Content
          </button>
        </div>
      </div>

      {/* Active Upload Jobs Progress */}
      {uploadJobs.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Upload Progress</h3>
          {uploadJobs.map(job => (
            <div key={job.id} className="flex items-center gap-3">
              {job.status === 'processing' || job.status === 'pending' ? (
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
              ) : job.status === 'success' ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-300 truncate">{job.filename}</span>
                  <span className="text-gray-500">{job.progress}%</span>
                </div>
                <div className="w-full bg-dark-300 rounded-full h-1.5 mt-1">
                  <div
                    className={`h-1.5 rounded-full transition-all duration-500 ${
                      job.status === 'failed' ? 'bg-red-500' :
                      job.status === 'success' ? 'bg-green-500' : 'bg-primary'
                    }`}
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {job.error || job.message}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Panel */}
      {showUpload && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex gap-2 mb-4 flex-wrap">
            {[
              { mode: 'file' as const, icon: Upload, label: 'Files' },
              { mode: 'image' as const, icon: Image, label: 'Images (OCR)' },
              { mode: 'url' as const, icon: Link, label: 'URL' },
              { mode: 'text' as const, icon: Type, label: 'Text' },
            ].map(({ mode, icon: Icon, label }) => (
              <button
                key={mode}
                onClick={() => setUploadMode(mode)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 ${uploadMode === mode ? 'bg-primary text-black' : 'bg-dark-200 text-gray-300 hover:bg-dark-300'}`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>

          {uploadMode === 'file' && (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-primary bg-primary/10' : 'border-dark-300 hover:border-dark-200'
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-12 h-12 mx-auto mb-4 text-gray-500" />
              {uploading ? (
                <p className="text-gray-400">Queuing files...</p>
              ) : isDragActive ? (
                <p className="text-primary">Drop files here</p>
              ) : (
                <p className="text-gray-400">Drag & drop files here, or click to select</p>
              )}
              <div className="text-xs text-gray-500 mt-4 space-y-1">
                <p><strong>Documents:</strong> PDF, DOCX, TXT, MD, CSV, XLSX, XLS, PPTX</p>
                <p><strong>Audio:</strong> MP3, WAV, M4A, OGG, FLAC (auto-transcribed)</p>
                <p><strong>Code:</strong> Python, JS, TS, Java, Go, Rust, C/C++, Ruby, PHP, and 20+ more</p>
                <p><strong>Data:</strong> JSON, YAML, XML, TOML, Jupyter notebooks</p>
                <p><strong>Other:</strong> ZIP archives, EPUB books, SRT/VTT subtitles</p>
              </div>
            </div>
          )}

          {uploadMode === 'image' && (
            <div
              {...getImageRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isImageDragActive ? 'border-primary bg-primary/10' : 'border-dark-300 hover:border-dark-200'
              }`}
            >
              <input {...getImageInputProps()} />
              <Image className="w-12 h-12 mx-auto mb-4 text-gray-500" />
              {uploading ? (
                <p className="text-gray-400">Queuing for OCR...</p>
              ) : isImageDragActive ? (
                <p className="text-primary">Drop images here</p>
              ) : (
                <p className="text-gray-400">Drag & drop images here, or click to select</p>
              )}
              <p className="text-xs text-gray-500 mt-2">PNG, JPG, JPEG, GIF, WebP, BMP, TIFF</p>
              <p className="text-xs text-primary mt-1">Text will be extracted using OCR</p>
            </div>
          )}

          {uploadMode === 'url' && (
            <div className="space-y-4">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="Enter URL (YouTube, web articles, GitHub repos, etc.)"
                className="input w-full"
              />
              <p className="text-xs text-gray-500">Supports: YouTube videos (transcribed), web articles, blog posts, documentation pages</p>
              <button onClick={uploadUrl} disabled={uploading} className="btn btn-primary">
                {uploading ? 'Queuing...' : 'Upload URL'}
              </button>
            </div>
          )}

          {uploadMode === 'text' && (
            <div className="space-y-4">
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Paste your content here (notes, articles, code snippets, etc.)..."
                rows={6}
                className="input w-full"
              />
              <button onClick={uploadText} disabled={uploading} className="btn btn-primary">
                {uploading ? 'Uploading...' : 'Upload Text'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <Filter className="w-4 h-4 text-gray-500" />
        <select
          value={filter.source_type}
          onChange={(e) => setFilter(f => ({ ...f, source_type: e.target.value }))}
          className="input w-auto"
        >
          <option value="">All Sources</option>
          {sourceTypes.map(type => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
        <select
          value={filter.skill_level}
          onChange={(e) => setFilter(f => ({ ...f, skill_level: e.target.value }))}
          className="input w-auto"
        >
          <option value="">All Levels</option>
          {skillLevels.map(level => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
      </div>

      {/* Documents List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="text-center py-12 bg-dark-100 rounded-xl border border-dark-300">
          <FileText className="w-12 h-12 mx-auto mb-4 text-gray-500" />
          <p className="text-gray-400">No documents found</p>
          <p className="text-sm text-gray-500">Upload some content to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredDocs.map(doc => (
            <div
              key={doc.id}
              className="bg-dark-100 rounded-lg border border-dark-300 p-4 hover:border-dark-200 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-dark-200 rounded-lg">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-200">{doc.title || `Document #${doc.id}`}</h3>
                    <div className="flex gap-2 mt-1">
                      <span className="badge badge-primary">{doc.source_type}</span>
                      {doc.skill_level && <span className="badge badge-success">{doc.skill_level}</span>}
                      <span className="text-xs text-gray-500">{new Date(doc.ingested_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => window.open(`/documents/${doc.id}`, '_blank')}
                    className="p-2 text-gray-400 hover:text-primary"
                    title="View document"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => downloadDocument(doc.id, doc.title || `document_${doc.id}`)}
                    className="p-2 text-gray-400 hover:text-green-500"
                    title="Download document"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteDocument(doc.id)}
                    className="p-2 text-gray-400 hover:text-accent-red"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1]);
    };
    reader.onerror = reject;
  });
}
