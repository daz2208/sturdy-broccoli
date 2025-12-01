'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  ArrowLeft,
  FileText,
  Tag as TagIcon,
  Plus,
  X,
  Download,
  Trash2,
  Loader2,
  Edit3,
  Save,
  Clock,
  Sparkles,
  Link2,
  ExternalLink,
  Search
} from 'lucide-react';
import type { Document, Tag, DocumentRelationship } from '@/types/api';

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const docId = parseInt(params.id as string);

  const [document, setDocument] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [documentTags, setDocumentTags] = useState<Tag[]>([]);
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [addingTag, setAddingTag] = useState(false);
  const [summaries, setSummaries] = useState<any[]>([]);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [relationships, setRelationships] = useState<DocumentRelationship[]>([]);
  const [discoveredDocs, setDiscoveredDocs] = useState<any[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [showAddRelationship, setShowAddRelationship] = useState(false);
  const [newRelationship, setNewRelationship] = useState({ targetDocId: '', type: 'related' });

  const loadDocument = useCallback(async () => {
    try {
      const data = await api.getDocument(docId);
      setDocument(data);
    } catch (err) {
      toast.error('Failed to load document');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [docId]);

  const loadAllTags = useCallback(async () => {
    try {
      const data = await api.getTags();
      setAllTags(data.tags);
    } catch (err) {
      console.error('Failed to load tags:', err);
    }
  }, []);

  const loadDocumentTags = useCallback(async () => {
    try {
      const data = await api.getDocumentTags(docId);
      setDocumentTags(data.tags);
    } catch (err) {
      console.error('Failed to load document tags:', err);
    }
  }, [docId]);

  const loadSummaries = useCallback(async () => {
    try {
      const data = await api.getDocumentSummaries(docId);
      setSummaries(data.summaries || []);
    } catch (err) {
      console.error('Failed to load summaries:', err);
    }
  }, [docId]);

  const addTag = async (tagId: number) => {
    setAddingTag(true);
    try {
      await api.addTagToDocument(docId, tagId);
      loadDocumentTags();
      setShowTagPicker(false);
      toast.success('Tag added');
    } catch (err) {
      toast.error('Failed to add tag');
      console.error(err);
    } finally {
      setAddingTag(false);
    }
  };

  const removeTag = async (tagId: number) => {
    try {
      await api.removeTagFromDocument(docId, tagId);
      setDocumentTags(prev => prev.filter(t => t.id !== tagId));
      toast.success('Tag removed');
    } catch (err) {
      toast.error('Failed to remove tag');
      console.error(err);
    }
  };

  const deleteDocument = async () => {
    if (!confirm('Delete this document? This action cannot be undone.')) return;
    try {
      await api.deleteDocument(docId);
      toast.success('Document deleted');
      router.push('/documents');
    } catch (err) {
      toast.error('Failed to delete document');
      console.error(err);
    }
  };

  const downloadDocument = async () => {
    try {
      await api.downloadDocument(docId, document?.title || `document_${docId}`);
      toast.success('Download started');
    } catch (err: any) {
      toast.error(`Download failed: ${err?.response?.data?.detail || err?.message || 'Unknown error'}`);
    }
  };

  const generateSummary = async () => {
    setGeneratingSummary(true);
    try {
      await api.summarizeDocument(docId);
      toast.success('Summary generated');
      loadSummaries();
    } catch (err) {
      toast.error('Failed to generate summary');
      console.error(err);
    } finally {
      setGeneratingSummary(false);
    }
  };

  const loadRelationships = useCallback(async () => {
    try {
      const data = await api.getRelationships(docId);
      setRelationships(data.relationships || []);
    } catch (err) {
      console.error('Failed to load relationships:', err);
    }
  }, [docId]);

  useEffect(() => {
    loadDocument();
    loadAllTags();
    loadDocumentTags();
    loadSummaries();
    loadRelationships();
  }, [docId, loadDocument, loadAllTags, loadDocumentTags, loadSummaries, loadRelationships]);

  const addRelationship = async () => {
    const targetId = parseInt(newRelationship.targetDocId);
    if (!targetId || isNaN(targetId)) {
      toast.error('Please enter a valid document ID');
      return;
    }
    try {
      await api.createRelationship(docId, targetId, newRelationship.type);
      toast.success('Relationship added');
      loadRelationships();
      setShowAddRelationship(false);
      setNewRelationship({ targetDocId: '', type: 'related' });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add relationship');
      console.error(err);
    }
  };

  const removeRelationship = async (targetDocId: number) => {
    if (!confirm('Remove this relationship?')) return;
    try {
      await api.deleteRelationship(docId, targetDocId);
      toast.success('Relationship removed');
      setRelationships(prev => prev.filter(r => r.target_doc_id !== targetDocId));
    } catch (err) {
      toast.error('Failed to remove relationship');
      console.error(err);
    }
  };

  const discoverRelated = async () => {
    setDiscovering(true);
    try {
      const data = await api.discoverRelatedDocuments(docId, 10, 0.3);
      setDiscoveredDocs(data.related_documents || []);
      if (data.related_documents?.length === 0) {
        toast('No similar documents found', { icon: '🔍' });
      } else {
        toast.success(`Found ${data.related_documents.length} related documents`);
      }
    } catch (err) {
      toast.error('Failed to discover related documents');
      console.error(err);
    } finally {
      setDiscovering(false);
    }
  };

  const availableTagsToAdd = allTags.filter(
    tag => !documentTags.find(dt => dt.id === tag.id)
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center py-16">
        <FileText className="w-12 h-12 mx-auto text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-300">Document not found</h3>
        <button onClick={() => router.push('/documents')} className="btn btn-primary mt-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Documents
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <button
            onClick={() => router.push('/documents')}
            className="flex items-center gap-2 text-gray-400 hover:text-gray-200 mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Documents
          </button>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
            <FileText className="w-6 h-6 text-accent-blue" />
            {document.title || `Document #${docId}`}
          </h1>
        </div>
        <div className="flex gap-2">
          <button onClick={downloadDocument} className="btn btn-secondary" title="Download">
            <Download className="w-4 h-4" />
          </button>
          <button onClick={deleteDocument} className="btn btn-danger" title="Delete">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Metadata */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Metadata</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-500">Source Type</p>
            <p className="text-gray-300 font-medium">{document.source_type || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Skill Level</p>
            <p className="text-gray-300 font-medium">{document.skill_level || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Cluster</p>
            <p className="text-gray-300 font-medium">{document.cluster?.name || 'Unclustered'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Ingested</p>
            <p className="text-gray-300 font-medium">
              {new Date(document.ingested_at).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>

      {/* Tags */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <TagIcon className="w-5 h-5 text-accent-blue" />
            Tags
          </h2>
          <button
            onClick={() => setShowTagPicker(!showTagPicker)}
            className="btn btn-sm btn-secondary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Tag
          </button>
        </div>

        {/* Current Tags */}
        <div className="flex flex-wrap gap-2 mb-4">
          {documentTags.length === 0 ? (
            <p className="text-gray-500 text-sm">No tags yet</p>
          ) : (
            documentTags.map(tag => (
              <div
                key={tag.id}
                className="px-3 py-1 rounded-full text-sm font-medium text-white flex items-center gap-2 group"
                style={{ backgroundColor: tag.color || '#3b82f6' }}
              >
                {tag.name}
                <button
                  onClick={() => removeTag(tag.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/20 rounded-full p-0.5"
                  title="Remove tag"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Tag Picker */}
        {showTagPicker && (
          <div className="border-t border-dark-300 pt-4">
            <p className="text-sm text-gray-500 mb-2">Available Tags:</p>
            {availableTagsToAdd.length === 0 ? (
              <p className="text-gray-500 text-sm">All tags are already added</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {availableTagsToAdd.map(tag => (
                  <button
                    key={tag.id}
                    onClick={() => addTag(tag.id)}
                    disabled={addingTag}
                    className="px-3 py-1 rounded-full text-sm font-medium text-white hover:opacity-80 transition-opacity disabled:opacity-50"
                    style={{ backgroundColor: tag.color || '#3b82f6' }}
                  >
                    {tag.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content Preview */}
      {document.content && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Content Preview</h2>
          <div className="bg-dark-200 rounded-lg p-4 max-h-96 overflow-y-auto">
            <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">
              {document.content.substring(0, 2000)}
              {document.content.length > 2000 && '...'}
            </pre>
          </div>
        </div>
      )}

      {/* Summaries */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-accent-purple" />
            Summaries
          </h2>
          <button
            onClick={generateSummary}
            disabled={generatingSummary}
            className="btn btn-sm btn-primary flex items-center gap-2"
          >
            {generatingSummary ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate Summary
              </>
            )}
          </button>
        </div>

        {summaries.length === 0 ? (
          <p className="text-gray-500 text-sm">No summaries yet. Click &quot;Generate Summary&quot; to create one.</p>
        ) : (
          <div className="space-y-3">
            {summaries.map((summary, idx) => (
              <div key={idx} className="bg-dark-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                  <Clock className="w-3 h-3" />
                  {new Date(summary.creation_date).toLocaleString()}
                </div>
                <p className="text-gray-300 text-sm leading-relaxed">{summary.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Relationships */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <Link2 className="w-5 h-5 text-accent-green" />
            Related Documents
          </h2>
          <div className="flex gap-2">
            <button
              onClick={discoverRelated}
              disabled={discovering}
              className="btn btn-sm btn-secondary flex items-center gap-2"
            >
              {discovering ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Discovering...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  Discover Similar
                </>
              )}
            </button>
            <button
              onClick={() => setShowAddRelationship(!showAddRelationship)}
              className="btn btn-sm btn-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Relationship
            </button>
          </div>
        </div>

        {/* Add Relationship Form */}
        {showAddRelationship && (
          <div className="border border-dark-300 rounded-lg p-4 mb-4 bg-dark-200">
            <p className="text-sm text-gray-400 mb-3">Link this document to another:</p>
            <div className="flex gap-3">
              <input
                type="number"
                value={newRelationship.targetDocId}
                onChange={(e) => setNewRelationship(prev => ({ ...prev, targetDocId: e.target.value }))}
                placeholder="Target Document ID"
                className="input flex-1"
              />
              <select
                value={newRelationship.type}
                onChange={(e) => setNewRelationship(prev => ({ ...prev, type: e.target.value }))}
                className="input w-auto"
              >
                <option value="related">Related</option>
                <option value="prerequisite">Prerequisite</option>
                <option value="extends">Extends</option>
                <option value="implements">Implements</option>
                <option value="references">References</option>
                <option value="similar">Similar</option>
              </select>
              <button onClick={addRelationship} className="btn btn-primary">
                Add
              </button>
              <button
                onClick={() => setShowAddRelationship(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Current Relationships */}
        {relationships.length === 0 && discoveredDocs.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No relationships yet. Click &quot;Discover Similar&quot; to find related documents or &quot;Add Relationship&quot; to manually link documents.
          </p>
        ) : (
          <div className="space-y-4">
            {/* Manual Relationships */}
            {relationships.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Linked Documents ({relationships.length})</h3>
                <div className="space-y-2">
                  {relationships.map((rel) => (
                    <div
                      key={rel.target_doc_id}
                      className="bg-dark-200 rounded-lg p-3 flex items-center justify-between group hover:border-primary/50 border border-transparent transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-4 h-4 text-accent-blue" />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-300">Document #{rel.target_doc_id}</span>
                            <span className="badge badge-sm" style={{ fontSize: '0.7rem' }}>
                              {rel.relationship_type}
                            </span>
                          </div>
                          {rel.strength && (
                            <p className="text-xs text-gray-500">Strength: {(rel.strength * 100).toFixed(0)}%</p>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => window.open(`/documents/${rel.target_doc_id}`, '_blank')}
                          className="btn btn-sm btn-secondary opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Open document"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => removeRelationship(rel.target_doc_id)}
                          className="btn btn-sm btn-error opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Remove relationship"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Discovered Documents */}
            {discoveredDocs.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">
                  Similar Documents ({discoveredDocs.length})
                </h3>
                <div className="space-y-2">
                  {discoveredDocs.map((doc) => (
                    <div
                      key={doc.doc_id}
                      className="bg-dark-200 rounded-lg p-3 flex items-center justify-between group hover:border-accent-green/50 border border-transparent transition-all"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <FileText className="w-4 h-4 text-accent-green flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-300 truncate">
                              {doc.filename || `Document #${doc.doc_id}`}
                            </span>
                            <span className="badge badge-sm badge-success" style={{ fontSize: '0.7rem' }}>
                              {(doc.similarity_score * 100).toFixed(0)}% match
                            </span>
                          </div>
                          <p className="text-xs text-gray-500">
                            {doc.source_type} • {doc.skill_level || 'N/A'}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => window.open(`/documents/${doc.doc_id}`, '_blank')}
                        className="btn btn-sm btn-secondary flex-shrink-0"
                        title="Open document"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
