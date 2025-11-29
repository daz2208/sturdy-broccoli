'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Copy,
  GitMerge,
  FileText,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Eye
} from 'lucide-react';
import type { DuplicateGroup } from '@/types/api';

export default function DuplicatesPage() {
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [threshold, setThreshold] = useState(0.85);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set());
  const [comparing, setComparing] = useState<{ doc1: number; doc2: number } | null>(null);
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const [merging, setMerging] = useState(false);

  useEffect(() => {
    findDuplicates();
  }, []);

  const findDuplicates = async () => {
    setScanning(true);
    try {
      const data = await api.findDuplicates(threshold, 50);
      setDuplicates(data.duplicate_groups || []);
      if ((data.duplicate_groups || []).length === 0) {
        toast.success('No duplicates found!');
      } else {
        toast.success(`Found ${data.duplicate_groups.length} duplicate groups`);
      }
    } catch (err) {
      toast.error('Failed to scan for duplicates');
      console.error(err);
    } finally {
      setScanning(false);
      setLoading(false);
    }
  };

  const compareDocs = async (doc1Id: number, doc2Id: number) => {
    setComparing({ doc1: doc1Id, doc2: doc2Id });
    setComparisonResult(null);
    try {
      const result = await api.compareDuplicates(doc1Id, doc2Id);
      setComparisonResult(result);
    } catch (err) {
      toast.error('Failed to compare documents');
      console.error(err);
    }
  };

  const mergeDocs = async (keepDocId: number, deleteDocIds: number[]) => {
    if (!confirm(`Keep document #${keepDocId} and delete ${deleteDocIds.length} duplicate(s)?`)) return;

    setMerging(true);
    try {
      const result = await api.mergeDuplicates(keepDocId, deleteDocIds);
      toast.success(`Merged ${result.merged_count} documents`);
      findDuplicates(); // Refresh the list
      setComparisonResult(null);
      setComparing(null);
    } catch (err) {
      toast.error('Failed to merge documents');
      console.error(err);
    } finally {
      setMerging(false);
    }
  };

  const toggleGroup = (index: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const getSimilarityColor = (score: number) => {
    if (score >= 0.95) return 'text-red-400';
    if (score >= 0.85) return 'text-orange-400';
    return 'text-yellow-400';
  };

  const getSimilarityBg = (score: number) => {
    if (score >= 0.95) return 'bg-red-500/20';
    if (score >= 0.85) return 'bg-orange-500/20';
    return 'bg-yellow-500/20';
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Copy className="w-6 h-6 text-accent-orange" />
            Duplicate Detection
          </h1>
          <p className="text-gray-500 mt-1">
            Find and merge duplicate or highly similar documents
          </p>
        </div>
        <button
          onClick={findDuplicates}
          disabled={scanning}
          className="btn btn-primary flex items-center gap-2"
        >
          {scanning ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Scan for Duplicates
            </>
          )}
        </button>
      </div>

      {/* Settings */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Detection Settings</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Similarity Threshold: {(threshold * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0.7"
              max="0.99"
              step="0.01"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>70% - More results</span>
              <span>99% - Exact matches only</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      {duplicates.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-sm text-gray-500">Duplicate Groups</p>
            <p className="text-2xl font-bold text-white">{duplicates.length}</p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-sm text-gray-500">Total Documents</p>
            <p className="text-2xl font-bold text-white">
              {duplicates.reduce((sum, group) => sum + group.group_size, 0)}
            </p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-sm text-gray-500">Avg Similarity</p>
            <p className="text-2xl font-bold text-white">
              {(
                duplicates.reduce((sum, group) => {
                  const avgSim = group.duplicates.reduce((s, d) => s + d.similarity, 0) / group.duplicates.length;
                  return sum + avgSim;
                }, 0) /
                duplicates.length *
                100
              ).toFixed(0)}%
            </p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-sm text-gray-500">Storage Impact</p>
            <p className="text-2xl font-bold text-white">
              {duplicates.reduce((sum, group) => sum + group.duplicates.length, 0)} docs
            </p>
          </div>
        </div>
      )}

      {/* Duplicate Groups */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-accent-orange" />
        </div>
      ) : duplicates.length === 0 ? (
        <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
          <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-4" />
          <h3 className="text-lg font-medium text-gray-300">No duplicates found</h3>
          <p className="text-gray-500 mt-2 max-w-md mx-auto">
            Your knowledge base is clean! Try adjusting the similarity threshold to find near-duplicates.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {duplicates.map((group, groupIdx) => (
            <div key={groupIdx} className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden">
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(groupIdx)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-dark-200 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {expandedGroups.has(groupIdx) ? (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  )}
                  <div className="text-left">
                    <h3 className="text-lg font-semibold text-gray-200">
                      Duplicate Group #{groupIdx + 1}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {group.group_size} similar documents
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {(() => {
                    const avgSim = group.duplicates.reduce((s, d) => s + d.similarity, 0) / group.duplicates.length;
                    return (
                      <>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${getSimilarityColor(avgSim)} ${getSimilarityBg(avgSim)}`}>
                          {(avgSim * 100).toFixed(1)}% similar
                        </span>
                        {avgSim >= 0.95 && (
                          <AlertTriangle className="w-5 h-5 text-red-400" />
                        )}
                      </>
                    );
                  })()}
                </div>
              </button>

              {/* Group Content */}
              {expandedGroups.has(groupIdx) && (
                <div className="border-t border-dark-300 p-6 space-y-4">
                  {/* Primary document */}
                  <div className="bg-dark-200 rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <FileText className="w-5 h-5 text-accent-blue mt-1" />
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium text-gray-200">
                              {group.primary_doc.title || `Document #${group.primary_doc.doc_id}`}
                            </h4>
                            <span className="badge badge-sm bg-green-500/20 text-green-400">Primary</span>
                          </div>
                          <div className="flex gap-2 mt-1">
                            {group.primary_doc.source_type && (
                              <span className="badge badge-primary">{group.primary_doc.source_type}</span>
                            )}
                            {group.primary_doc.skill_level && (
                              <span className="badge badge-success">{group.primary_doc.skill_level}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        {group.duplicates.length > 0 && (
                          <button
                            onClick={() =>
                              mergeDocs(
                                group.primary_doc.doc_id,
                                group.duplicates.map(d => d.doc_id)
                              )
                            }
                            disabled={merging}
                            className="btn btn-sm bg-green-500/20 text-green-400 hover:bg-green-500/30"
                            title="Keep this, delete others"
                          >
                            {merging ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <GitMerge className="w-4 h-4 mr-1" />
                                Keep This
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Duplicate documents */}
                  {group.duplicates.map((doc) => (
                    <div key={doc.doc_id} className="bg-dark-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <FileText className="w-5 h-5 text-accent-orange mt-1" />
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium text-gray-200">
                                {doc.title || `Document #${doc.doc_id}`}
                              </h4>
                              <span className="badge badge-sm bg-orange-500/20 text-orange-400">
                                {(doc.similarity * 100).toFixed(1)}% match
                              </span>
                            </div>
                            <div className="flex gap-2 mt-1">
                              {doc.source_type && (
                                <span className="badge badge-primary">{doc.source_type}</span>
                              )}
                              {doc.skill_level && (
                                <span className="badge badge-success">{doc.skill_level}</span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => compareDocs(group.primary_doc.doc_id, doc.doc_id)}
                            className="btn btn-sm btn-secondary"
                            title="Compare with primary document"
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            Compare
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Comparison Modal */}
      {comparisonResult && comparing && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-dark-100 rounded-2xl border border-dark-300 max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-6 border-b border-dark-300 flex justify-between items-center">
              <h2 className="text-xl font-bold text-white">Document Comparison</h2>
              <button
                onClick={() => {
                  setComparing(null);
                  setComparisonResult(null);
                }}
                className="text-gray-400 hover:text-white"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              <div className="flex items-center justify-center">
                <span className={`px-6 py-3 rounded-full text-lg font-bold ${getSimilarityColor(comparisonResult.similarity_score)} ${getSimilarityBg(comparisonResult.similarity_score)}`}>
                  {(comparisonResult.similarity_score * 100).toFixed(1)}% Similar
                </span>
              </div>

              {comparisonResult.content_comparison && (
                <>
                  {/* Matches */}
                  {comparisonResult.content_comparison.matches?.length > 0 && (
                    <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-4">
                      <h3 className="text-green-400 font-semibold mb-3 flex items-center gap-2">
                        <CheckCircle className="w-5 h-5" />
                        Matching Content ({comparisonResult.content_comparison.matches.length})
                      </h3>
                      <ul className="space-y-2">
                        {comparisonResult.content_comparison.matches.map((match: string, idx: number) => (
                          <li key={idx} className="text-sm text-gray-300">• {match}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Differences */}
                  {comparisonResult.content_comparison.differences?.length > 0 && (
                    <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
                      <h3 className="text-yellow-400 font-semibold mb-3 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        Differences ({comparisonResult.content_comparison.differences.length})
                      </h3>
                      <ul className="space-y-2">
                        {comparisonResult.content_comparison.differences.map((diff: string, idx: number) => (
                          <li key={idx} className="text-sm text-gray-300">• {diff}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="p-6 border-t border-dark-300 flex justify-end gap-3">
              <button
                onClick={() => {
                  setComparing(null);
                  setComparisonResult(null);
                }}
                className="btn btn-secondary"
              >
                Close
              </button>
              <button
                onClick={() => mergeDocs(comparing.doc1, [comparing.doc2])}
                disabled={merging}
                className="btn btn-primary"
              >
                {merging ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Merging...
                  </>
                ) : (
                  <>
                    <GitMerge className="w-4 h-4 mr-2" />
                    Merge Documents
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
