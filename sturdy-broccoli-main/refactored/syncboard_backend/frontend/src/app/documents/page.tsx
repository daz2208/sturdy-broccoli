'use client';

import { useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { FileText, Upload, Trash2, ExternalLink, Filter } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import type { Document } from '@/types/api';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadMode, setUploadMode] = useState<'file' | 'url' | 'text'>('file');
  const [textContent, setTextContent] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [filter, setFilter] = useState({ source_type: '', skill_level: '' });

  useEffect(() => {
    loadDocuments();
  }, []);

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

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);
    let successCount = 0;

    for (const file of acceptedFiles) {
      try {
        const base64 = await fileToBase64(file);
        await api.uploadFile(base64, file.name);
        successCount++;
      } catch (err) {
        console.error(`Failed to upload ${file.name}:`, err);
      }
    }

    toast.success(`Uploaded ${successCount}/${acceptedFiles.length} files`);
    setUploading(false);
    loadDocuments();
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt', '.md'],
      'audio/*': ['.mp3', '.wav', '.m4a'],
      'application/json': ['.json', '.ipynb'],
    },
  });

  const uploadText = async () => {
    if (!textContent.trim()) {
      toast.error('Please enter some content');
      return;
    }
    setUploading(true);
    try {
      await api.uploadText(textContent);
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
      await api.uploadUrl(urlInput);
      toast.success('URL processed successfully');
      setUrlInput('');
      loadDocuments();
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
          <h1 className="text-2xl font-bold text-gray-100">Documents</h1>
          <p className="text-gray-500">{documents.length} documents in your knowledge base</p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Upload className="w-4 h-4" />
          Upload Content
        </button>
      </div>

      {/* Upload Panel */}
      {showUpload && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex gap-4 mb-4">
            {(['file', 'url', 'text'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setUploadMode(mode)}
                className={`px-4 py-2 rounded-lg ${uploadMode === mode ? 'bg-primary text-black' : 'bg-dark-200 text-gray-300'}`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
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
                <p className="text-gray-400">Uploading...</p>
              ) : isDragActive ? (
                <p className="text-primary">Drop files here</p>
              ) : (
                <p className="text-gray-400">Drag & drop files here, or click to select</p>
              )}
              <p className="text-xs text-gray-500 mt-2">PDF, TXT, MD, Audio, Jupyter notebooks, and more</p>
            </div>
          )}

          {uploadMode === 'url' && (
            <div className="space-y-4">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="Enter URL (YouTube, web articles, etc.)"
                className="input"
              />
              <button onClick={uploadUrl} disabled={uploading} className="btn btn-primary">
                {uploading ? 'Processing...' : 'Upload URL'}
              </button>
            </div>
          )}

          {uploadMode === 'text' && (
            <div className="space-y-4">
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Paste your content here..."
                rows={6}
                className="input"
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
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteDocument(doc.id)}
                    className="p-2 text-gray-400 hover:text-accent-red"
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
