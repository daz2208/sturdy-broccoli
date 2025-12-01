'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Network,
  Brain,
  Code2,
  TrendingUp,
  Search,
  Loader2,
  RefreshCw,
  FileText,
  Sparkles,
  ArrowRight,
  Tag,
  Cpu,
  MapPin
} from 'lucide-react';
import type { KnowledgeGraphStats, ConceptCloud } from '@/types/api';

export default function KnowledgeGraphPage() {
  const [stats, setStats] = useState<KnowledgeGraphStats | null>(null);
  const [concepts, setConcepts] = useState<ConceptCloud[]>([]);
  const [technologies, setTechnologies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'concepts' | 'tech' | 'path'>('overview');

  // Learning path state
  const [pathForm, setPathForm] = useState({ start: '', end: '' });
  const [learningPath, setLearningPath] = useState<any>(null);
  const [findingPath, setFindingPath] = useState(false);

  // Document explorer state
  const [selectedConcept, setSelectedConcept] = useState('');
  const [selectedTech, setSelectedTech] = useState('');
  const [conceptDocs, setConceptDocs] = useState<any[]>([]);
  const [techDocs, setTechDocs] = useState<any[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  useEffect(() => {
    loadGraphData();
  }, []);

  const loadGraphData = async () => {
    setLoading(true);
    try {
      const [statsRes, conceptsRes, techRes] = await Promise.all([
        api.getKnowledgeGraphStats(),
        api.getConcepts(50),
        api.getTechnologies(50)
      ]);

      setStats(statsRes.stats);
      setConcepts(conceptsRes.concepts || []);
      setTechnologies(techRes.technologies || []);
    } catch (err) {
      console.error('Failed to load graph data:', err);
      toast.error('Failed to load knowledge graph');
    } finally {
      setLoading(false);
    }
  };

  const buildGraph = async () => {
    setBuilding(true);
    try {
      const result = await api.buildKnowledgeGraph();
      toast.success('Knowledge graph built successfully!');
      setStats(result.stats);
      loadGraphData(); // Reload all data
    } catch (err) {
      toast.error('Failed to build graph');
      console.error(err);
    } finally {
      setBuilding(false);
    }
  };

  const findPath = async () => {
    if (!pathForm.start.trim() || !pathForm.end.trim()) {
      toast.error('Please enter both start and end concepts');
      return;
    }

    setFindingPath(true);
    try {
      const result = await api.findLearningPath(pathForm.start, pathForm.end);
      setLearningPath(result);
      if (result.found) {
        toast.success(`Found path with ${result.steps} steps!`);
      } else {
        toast('No path found', { icon: '🔍' });
      }
    } catch (err) {
      toast.error('Failed to find learning path');
      console.error(err);
    } finally {
      setFindingPath(false);
    }
  };

  const exploreConcept = async (concept: string) => {
    setSelectedConcept(concept);
    setLoadingDocs(true);
    try {
      const result = await api.getDocumentsByConcept(concept, 20);
      setConceptDocs(result.documents || []);
    } catch (err) {
      toast.error('Failed to load documents');
      console.error(err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const exploreTech = async (tech: string) => {
    setSelectedTech(tech);
    setLoadingDocs(true);
    try {
      const result = await api.getDocumentsByTech(tech, 20);
      setTechDocs(result.documents || []);
    } catch (err) {
      toast.error('Failed to load documents');
      console.error(err);
    } finally {
      setLoadingDocs(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
            <Network className="w-7 h-7 text-accent-purple" />
            Knowledge Graph
          </h1>
          <p className="text-gray-500 mt-1">
            Visualize connections between documents, concepts, and technologies
          </p>
        </div>
        <button
          onClick={buildGraph}
          disabled={building}
          className="btn btn-primary flex items-center gap-2"
        >
          {building ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Building...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Rebuild Graph
            </>
          )}
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 rounded-xl border border-blue-500/20 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Documents</p>
                <p className="text-3xl font-bold text-gray-100 mt-2">
                  {stats.total_documents}
                </p>
              </div>
              <FileText className="w-12 h-12 text-blue-400 opacity-50" />
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 rounded-xl border border-purple-500/20 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Relationships</p>
                <p className="text-3xl font-bold text-gray-100 mt-2">
                  {stats.total_relationships}
                </p>
              </div>
              <Network className="w-12 h-12 text-purple-400 opacity-50" />
            </div>
          </div>

          <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 rounded-xl border border-green-500/20 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Concepts</p>
                <p className="text-3xl font-bold text-gray-100 mt-2">
                  {stats.unique_concepts}
                </p>
              </div>
              <Brain className="w-12 h-12 text-green-400 opacity-50" />
            </div>
          </div>

          <div className="bg-gradient-to-br from-orange-500/10 to-orange-600/5 rounded-xl border border-orange-500/20 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Technologies</p>
                <p className="text-3xl font-bold text-gray-100 mt-2">
                  {stats.unique_technologies}
                </p>
              </div>
              <Code2 className="w-12 h-12 text-orange-400 opacity-50" />
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden">
        <div className="flex border-b border-dark-300">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex-1 px-6 py-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'overview'
                ? 'bg-primary/10 text-primary border-b-2 border-primary'
                : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            Overview
          </button>
          <button
            onClick={() => setActiveTab('concepts')}
            className={`flex-1 px-6 py-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'concepts'
                ? 'bg-primary/10 text-primary border-b-2 border-primary'
                : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
            }`}
          >
            <Tag className="w-4 h-4" />
            Concepts ({concepts.length})
          </button>
          <button
            onClick={() => setActiveTab('tech')}
            className={`flex-1 px-6 py-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'tech'
                ? 'bg-primary/10 text-primary border-b-2 border-primary'
                : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
            }`}
          >
            <Cpu className="w-4 h-4" />
            Tech Stack ({technologies.length})
          </button>
          <button
            onClick={() => setActiveTab('path')}
            className={`flex-1 px-6 py-4 flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'path'
                ? 'bg-primary/10 text-primary border-b-2 border-primary'
                : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
            }`}
          >
            <MapPin className="w-4 h-4" />
            Learning Paths
          </button>
        </div>

        <div className="p-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-accent-purple" />
                  Top Concepts
                </h3>
                <div className="flex flex-wrap gap-2">
                  {concepts.slice(0, 20).map((concept, idx) => {
                    const size = Math.max(12, Math.min(24, concept.frequency / 2));
                    return (
                      <button
                        key={idx}
                        onClick={() => {
                          setActiveTab('concepts');
                          exploreConcept(concept.concept);
                        }}
                        className="px-4 py-2 rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-all hover:scale-105"
                        style={{ fontSize: `${size}px` }}
                      >
                        {concept.concept}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                  <Code2 className="w-5 h-5 text-accent-orange" />
                  Top Technologies
                </h3>
                <div className="flex flex-wrap gap-2">
                  {technologies.slice(0, 20).map((tech, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setActiveTab('tech');
                        exploreTech(tech.tech);
                      }}
                      className="px-4 py-2 rounded-lg bg-accent-orange/10 text-accent-orange border border-accent-orange/20 hover:bg-accent-orange/20 transition-all hover:scale-105"
                    >
                      {tech.tech}
                      <span className="ml-2 text-xs opacity-60">({tech.frequency})</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Concepts Tab */}
          {activeTab === 'concepts' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {concepts.map((concept, idx) => (
                  <button
                    key={idx}
                    onClick={() => exploreConcept(concept.concept)}
                    className={`p-4 rounded-lg border transition-all text-left hover:scale-105 ${
                      selectedConcept === concept.concept
                        ? 'bg-primary/20 border-primary text-primary'
                        : 'bg-dark-200 border-dark-300 text-gray-300 hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{concept.concept}</span>
                      <span className="text-sm opacity-60">×{concept.frequency}</span>
                    </div>
                  </button>
                ))}
              </div>

              {/* Documents for selected concept */}
              {selectedConcept && (
                <div className="mt-6 bg-dark-200 rounded-lg border border-dark-300 p-4">
                  <h4 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary" />
                    Documents covering &quot;{selectedConcept}&quot; ({conceptDocs.length})
                  </h4>
                  {loadingDocs ? (
                    <div className="flex justify-center py-4">
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {conceptDocs.map((doc) => (
                        <div
                          key={doc.doc_id}
                          onClick={() => window.open(`/documents/${doc.doc_id}`, '_blank')}
                          className="p-3 bg-dark-100 rounded border border-dark-300 hover:border-primary/50 cursor-pointer transition-all"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-gray-300">{doc.title || `Document #${doc.doc_id}`}</span>
                            {doc.relevance && (
                              <span className="text-xs text-gray-500">
                                {(doc.relevance * 100).toFixed(0)}% relevance
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tech Stack Tab */}
          {activeTab === 'tech' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {technologies.map((tech, idx) => (
                  <button
                    key={idx}
                    onClick={() => exploreTech(tech.tech)}
                    className={`p-4 rounded-lg border transition-all text-left hover:scale-105 ${
                      selectedTech === tech.tech
                        ? 'bg-accent-orange/20 border-accent-orange text-accent-orange'
                        : 'bg-dark-200 border-dark-300 text-gray-300 hover:border-accent-orange/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{tech.tech}</span>
                      <span className="text-sm opacity-60">×{tech.frequency}</span>
                    </div>
                  </button>
                ))}
              </div>

              {/* Documents for selected tech */}
              {selectedTech && (
                <div className="mt-6 bg-dark-200 rounded-lg border border-dark-300 p-4">
                  <h4 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
                    <Code2 className="w-4 h-4 text-accent-orange" />
                    Documents using &quot;{selectedTech}&quot; ({techDocs.length})
                  </h4>
                  {loadingDocs ? (
                    <div className="flex justify-center py-4">
                      <Loader2 className="w-5 h-5 animate-spin text-accent-orange" />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {techDocs.map((doc) => (
                        <div
                          key={doc.doc_id}
                          onClick={() => window.open(`/documents/${doc.doc_id}`, '_blank')}
                          className="p-3 bg-dark-100 rounded border border-dark-300 hover:border-accent-orange/50 cursor-pointer transition-all"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-gray-300">{doc.title || `Document #${doc.doc_id}`}</span>
                            {doc.relevance && (
                              <span className="text-xs text-gray-500">
                                {(doc.relevance * 100).toFixed(0)}% relevance
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Learning Path Tab */}
          {activeTab === 'path' && (
            <div className="space-y-6">
              <div className="bg-dark-200 rounded-lg border border-dark-300 p-6">
                <h3 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                  <Search className="w-5 h-5 text-accent-green" />
                  Find Learning Path
                </h3>
                <p className="text-sm text-gray-400 mb-4">
                  Discover the shortest path between two concepts in your knowledge base
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={pathForm.start}
                    onChange={(e) => setPathForm(prev => ({ ...prev, start: e.target.value }))}
                    placeholder="Start concept (e.g., python basics)"
                    className="input flex-1"
                  />
                  <ArrowRight className="w-6 h-6 text-gray-500 mt-3" />
                  <input
                    type="text"
                    value={pathForm.end}
                    onChange={(e) => setPathForm(prev => ({ ...prev, end: e.target.value }))}
                    placeholder="End concept (e.g., machine learning)"
                    className="input flex-1"
                  />
                  <button
                    onClick={findPath}
                    disabled={findingPath}
                    className="btn btn-primary px-8"
                  >
                    {findingPath ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Finding...
                      </>
                    ) : (
                      'Find Path'
                    )}
                  </button>
                </div>
              </div>

              {/* Learning Path Results */}
              {learningPath && (
                <div className="bg-dark-200 rounded-lg border border-dark-300 p-6">
                  {learningPath.found ? (
                    <>
                      <h3 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-accent-green" />
                        Learning Path Found ({learningPath.steps} steps)
                      </h3>
                      <div className="space-y-3">
                        {learningPath.path.map((step: any, idx: number) => (
                          <div key={idx} className="flex items-center gap-4">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-green/20 text-accent-green flex items-center justify-center font-semibold">
                              {idx + 1}
                            </div>
                            <div className="flex-1 bg-dark-100 rounded-lg border border-dark-300 p-4">
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-gray-200">
                                  {step.title || step.concept || `Document #${step.doc_id}`}
                                </span>
                                {step.doc_id && (
                                  <button
                                    onClick={() => window.open(`/documents/${step.doc_id}`, '_blank')}
                                    className="btn btn-sm btn-secondary"
                                  >
                                    Open
                                  </button>
                                )}
                              </div>
                              {step.distance !== undefined && (
                                <p className="text-xs text-gray-500 mt-1">
                                  Distance: {step.distance}
                                </p>
                              )}
                            </div>
                            {idx < learningPath.path.length - 1 && (
                              <ArrowRight className="w-5 h-5 text-gray-600" />
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-8">
                      <Search className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                      <p className="text-gray-400">
                        {learningPath.message || 'No path found between these concepts'}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
