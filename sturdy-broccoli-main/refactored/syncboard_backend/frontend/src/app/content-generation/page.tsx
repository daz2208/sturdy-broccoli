'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { useRequireAuth } from '@/hooks/useRequireAuth';
import {
  FileText,
  Sparkles,
  Download,
  Copy,
  Briefcase,
  BookOpen,
  Zap,
  CheckCircle,
  FileCheck,
  Loader2
} from 'lucide-react';
import type {
  Industry,
  ContentTemplate,
  ContentGenerationResponse
} from '@/types/api';

export default function ContentGenerationPage() {
  const isReady = useRequireAuth();

  // State management
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');
  const [templates, setTemplates] = useState<ContentTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [topic, setTopic] = useState('');
  const [targetLength, setTargetLength] = useState<'short' | 'medium' | 'long'>('medium');
  const [includeCitations, setIncludeCitations] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadingIndustries, setLoadingIndustries] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<ContentGenerationResponse | null>(null);
  const [currentKBIndustry, setCurrentKBIndustry] = useState<Industry | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Load industries on mount
  useEffect(() => {
    if (!isReady) return; // Wait for auth to be ready!
    loadIndustries();
    loadCurrentKBIndustry();
    loadDocuments();
  }, [isReady]);

  // Load templates when industry changes
  useEffect(() => {
    if (selectedIndustry) {
      loadTemplates(selectedIndustry);
    } else {
      setTemplates([]);
      setSelectedTemplate('');
    }
  }, [selectedIndustry]);

  const loadIndustries = async () => {
    try {
      setLoadingIndustries(true);
      const response = await api.listIndustries();
      setIndustries(response.industries);
    } catch (err) {
      toast.error('Failed to load industries');
      console.error(err);
    } finally {
      setLoadingIndustries(false);
    }
  };

  const loadCurrentKBIndustry = async () => {
    try {
      const response = await api.getKBIndustry();
      if (response.industry) {
        setCurrentKBIndustry(response.industry);
        setSelectedIndustry(response.industry.id);
      }
    } catch (err) {
      console.error('Failed to load current KB industry:', err);
    }
  };

  const loadTemplates = async (industry: string) => {
    try {
      const response = await api.getIndustryTemplates(industry);
      setTemplates(response.templates);
      if (response.templates.length > 0) {
        setSelectedTemplate(response.templates[0].name);
      }
    } catch (err) {
      toast.error('Failed to load templates');
      console.error(err);
    }
  };

  const loadDocuments = async () => {
    try {
      setLoadingDocuments(true);
      const response = await api.getDocuments();
      setDocuments(response.documents || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
      toast.error('Failed to load documents');
    } finally {
      setLoadingDocuments(false);
    }
  };

  const toggleDocumentSelection = (docId: string) => {
    setSelectedDocIds(prev =>
      prev.includes(docId)
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    );
  };

  const selectAllDocuments = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map(doc => doc.doc_id));
    }
  };

  const handleGenerate = async () => {
    if (!selectedIndustry) {
      toast.error('Please select an industry');
      return;
    }
    if (!selectedTemplate) {
      toast.error('Please select a template');
      return;
    }

    setLoading(true);
    try {
      const response = await api.generateContent({
        template_name: selectedTemplate,
        topic: topic || undefined,
        target_length: targetLength,
        include_citations: includeCitations,
        doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      }, selectedIndustry);

      setGeneratedContent(response);
      toast.success('Content generated successfully!');
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      if (errorMessage.includes('OpenAI') || errorMessage.includes('API key')) {
        toast.error('AI service not configured. Check OPENAI_API_KEY.');
      } else {
        toast.error('Failed to generate content');
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateSummary = async () => {
    setLoading(true);
    try {
      const response = await api.generateSummary(topic || undefined);
      setGeneratedContent(response);
      toast.success('Summary generated!');
    } catch (err) {
      toast.error('Failed to generate summary');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateAnalysis = async () => {
    setLoading(true);
    try {
      const response = await api.generateAnalysis(topic || undefined);
      setGeneratedContent(response);
      toast.success('Analysis generated!');
    } catch (err) {
      toast.error('Failed to generate analysis');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSetAsDefault = async () => {
    if (!selectedIndustry) return;

    try {
      await api.setKBIndustry(selectedIndustry);
      setCurrentKBIndustry(industries.find(i => i.id === selectedIndustry) || null);
      toast.success('Default industry set!');
    } catch (err) {
      toast.error('Failed to set default industry');
      console.error(err);
    }
  };

  const copyToClipboard = () => {
    if (!generatedContent) return;

    const fullText = `${generatedContent.title}\n\n${generatedContent.sections.map(s =>
      `${s.title}\n${s.content}${s.citations ? '\n\nCitations:\n' + s.citations.join('\n') : ''}`
    ).join('\n\n')}`;

    navigator.clipboard.writeText(fullText);
    toast.success('Copied to clipboard!');
  };

  const downloadAsMarkdown = () => {
    if (!generatedContent) return;

    const markdown = `# ${generatedContent.title}\n\n${generatedContent.sections.map(s =>
      `## ${s.title}\n\n${s.content}${s.citations ? '\n\n### Citations\n' + s.citations.map(c => `- ${c}`).join('\n') : ''}`
    ).join('\n\n')}

---

**Generated by SyncBoard**
Industry: ${generatedContent.metadata.industry}
Template: ${generatedContent.metadata.template_used}
Word Count: ${generatedContent.metadata.word_count}
Sources: ${generatedContent.metadata.sources_used}
Date: ${new Date(generatedContent.metadata.generated_at).toLocaleDateString()}
`;

    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${generatedContent.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Downloaded as Markdown!');
  };

  // Show loading while auth is initializing
  if (!isReady) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-100 flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-accent-purple" />
            Content Generation
          </h1>
          <p className="text-gray-500 mt-1">
            Generate professional content from your knowledge base with industry-specific templates
          </p>
        </div>
        {currentKBIndustry && (
          <div className="bg-accent-green/20 border border-accent-green/40 rounded-lg px-4 py-2">
            <p className="text-sm text-gray-400">Default Industry</p>
            <p className="font-semibold text-accent-green">{currentKBIndustry.name}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Panel - Configuration */}
        <div className="lg:col-span-1 space-y-4">
          {/* Industry Selector */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Briefcase className="w-5 h-5 text-accent-purple" />
              <h2 className="text-lg font-semibold text-gray-200">Industry</h2>
            </div>

            {loadingIndustries ? (
              <div className="animate-pulse space-y-2">
                <div className="h-10 bg-dark-200 rounded"></div>
              </div>
            ) : (
              <>
                <select
                  value={selectedIndustry}
                  onChange={(e) => setSelectedIndustry(e.target.value)}
                  className="w-full px-4 py-2 bg-dark-200 border border-dark-300 rounded-lg text-gray-200 focus:outline-none focus:border-primary"
                >
                  <option value="">Select Industry</option>
                  {industries.map(industry => (
                    <option key={industry.id} value={industry.id}>
                      {industry.name}
                    </option>
                  ))}
                </select>
                {selectedIndustry && (
                  <button
                    onClick={handleSetAsDefault}
                    className="mt-2 w-full text-sm text-accent-purple hover:text-accent-purple/80 transition-colors"
                  >
                    Set as default for KB
                  </button>
                )}
              </>
            )}
          </div>

          {/* Template Selector */}
          {selectedIndustry && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="w-5 h-5 text-accent-blue" />
                <h2 className="text-lg font-semibold text-gray-200">Template</h2>
              </div>

              <div className="space-y-2">
                {templates.map(template => (
                  <label
                    key={template.name}
                    className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedTemplate === template.name
                        ? 'bg-primary/20 border-2 border-primary'
                        : 'bg-dark-200 border-2 border-transparent hover:border-dark-400'
                    }`}
                  >
                    <input
                      type="radio"
                      name="template"
                      value={template.name}
                      checked={selectedTemplate === template.name}
                      onChange={(e) => setSelectedTemplate(e.target.value)}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <p className="font-medium text-gray-200">{template.name}</p>
                      <p className="text-sm text-gray-500">{template.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Document Selection */}
          {selectedTemplate && documents.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-accent-green" />
                  <h2 className="text-lg font-semibold text-gray-200">Source Documents</h2>
                </div>
                <button
                  onClick={selectAllDocuments}
                  className="text-sm text-accent-purple hover:text-accent-purple/80 transition-colors"
                >
                  {selectedDocIds.length === documents.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>

              {loadingDocuments ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-10 bg-dark-200 rounded"></div>
                  <div className="h-10 bg-dark-200 rounded"></div>
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {documents.slice(0, 20).map((doc) => (
                    <label
                      key={doc.doc_id}
                      className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedDocIds.includes(doc.doc_id)
                          ? 'bg-accent-green/20 border-2 border-accent-green'
                          : 'bg-dark-200 border-2 border-transparent hover:border-dark-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocIds.includes(doc.doc_id)}
                        onChange={() => toggleDocumentSelection(doc.doc_id)}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-200 truncate">
                          {doc.filename || doc.title || `Document ${doc.doc_id}`}
                        </p>
                        <p className="text-xs text-gray-500">
                          {doc.source_type} • {doc.skill_level || 'unknown'}
                        </p>
                      </div>
                    </label>
                  ))}
                  {documents.length > 20 && (
                    <p className="text-xs text-gray-500 text-center pt-2">
                      Showing first 20 of {documents.length} documents
                    </p>
                  )}
                </div>
              )}

              {selectedDocIds.length > 0 && (
                <div className="mt-3 pt-3 border-t border-dark-300">
                  <p className="text-sm text-gray-400">
                    {selectedDocIds.length} document{selectedDocIds.length !== 1 ? 's' : ''} selected
                    {selectedDocIds.length === 0 && ' (will use all available documents)'}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Generation Options */}
          {selectedTemplate && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="w-5 h-5 text-accent-orange" />
                <h2 className="text-lg font-semibold text-gray-200">Options</h2>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Topic (optional)</label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Enter a specific topic"
                    className="w-full px-4 py-2 bg-dark-200 border border-dark-300 rounded-lg text-gray-200 placeholder-gray-600 focus:outline-none focus:border-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-2">Length</label>
                  <select
                    value={targetLength}
                    onChange={(e) => setTargetLength(e.target.value as any)}
                    className="w-full px-4 py-2 bg-dark-200 border border-dark-300 rounded-lg text-gray-200 focus:outline-none focus:border-primary"
                  >
                    <option value="short">Short (~500 words)</option>
                    <option value="medium">Medium (~1000 words)</option>
                    <option value="long">Long (~2000 words)</option>
                  </select>
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeCitations}
                    onChange={(e) => setIncludeCitations(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-gray-300">Include citations</span>
                </label>
              </div>

              <button
                onClick={handleGenerate}
                disabled={loading || !selectedTemplate}
                className="w-full mt-6 btn btn-primary flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Content
                  </>
                )}
              </button>

              {/* Quick Actions */}
              <div className="mt-4 pt-4 border-t border-dark-300">
                <p className="text-xs text-gray-500 mb-2">Quick Generate:</p>
                <div className="flex gap-2">
                  <button
                    onClick={handleGenerateSummary}
                    disabled={loading}
                    className="flex-1 text-xs px-3 py-2 bg-dark-200 hover:bg-dark-300 rounded-lg text-gray-300 transition-colors"
                  >
                    Summary
                  </button>
                  <button
                    onClick={handleGenerateAnalysis}
                    disabled={loading}
                    className="flex-1 text-xs px-3 py-2 bg-dark-200 hover:bg-dark-300 rounded-lg text-gray-300 transition-colors"
                  >
                    Analysis
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel - Generated Content */}
        <div className="lg:col-span-2">
          {generatedContent ? (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-8 space-y-6">
              {/* Header with Actions */}
              <div className="flex justify-between items-start gap-4">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-gray-100 mb-2">
                    {generatedContent.title}
                  </h2>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <span>{generatedContent.metadata.word_count} words</span>
                    <span>•</span>
                    <span>{generatedContent.metadata.sources_used} sources</span>
                    <span>•</span>
                    <span>{generatedContent.metadata.industry}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={copyToClipboard}
                    className="btn btn-secondary flex items-center gap-2"
                    title="Copy to clipboard"
                  >
                    <Copy className="w-4 h-4" />
                    Copy
                  </button>
                  <button
                    onClick={downloadAsMarkdown}
                    className="btn btn-primary flex items-center gap-2"
                    title="Download as Markdown"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </button>
                </div>
              </div>

              {/* Content Sections */}
              <div className="space-y-6 prose prose-invert max-w-none">
                {generatedContent.sections.map((section, idx) => (
                  <div key={idx} className="border-b border-dark-300 pb-6 last:border-0">
                    <h3 className="text-xl font-semibold text-gray-200 mb-3">
                      {section.title}
                    </h3>
                    <div className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {section.content}
                    </div>
                    {section.citations && section.citations.length > 0 && (
                      <div className="mt-4 pl-4 border-l-2 border-accent-blue">
                        <p className="text-sm font-medium text-gray-400 mb-2">Citations:</p>
                        <ul className="text-sm text-gray-500 space-y-1">
                          {section.citations.map((citation, cidx) => (
                            <li key={cidx}>{citation}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Metadata Footer */}
              <div className="pt-6 border-t border-dark-300">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <CheckCircle className="w-4 h-4 text-accent-green" />
                  Generated using <span className="text-gray-400 font-medium">{generatedContent.metadata.template_used}</span> template
                  <span>•</span>
                  <span>{new Date(generatedContent.metadata.generated_at).toLocaleString()}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-12 h-full flex flex-col items-center justify-center text-center">
              <FileText className="w-20 h-20 text-gray-600 mb-4" />
              <h3 className="text-xl font-semibold text-gray-300 mb-2">
                No Content Generated Yet
              </h3>
              <p className="text-gray-500 max-w-md">
                Select an industry and template from the left panel, then click &quot;Generate Content&quot; to create professional documents from your knowledge base.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
