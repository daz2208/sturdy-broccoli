'use client';
import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Lightbulb,
  Loader2,
  ChevronDown,
  ChevronRight,
  Code,
  FolderTree,
  BookOpen,
  ListChecks,
  ExternalLink,
  AlertTriangle,
  Target,
  Clock,
  Gauge,
  Copy,
  Check,
  Bookmark,
  Sparkles
} from 'lucide-react';

interface BuildSuggestion {
  title: string;
  description: string;
  feasibility: string;
  effort_estimate: string;
  complexity_level?: string;
  required_skills: string[];
  missing_knowledge?: string[];
  relevant_clusters?: number[];
  starter_steps?: string[];
  file_structure?: string;
  starter_code?: string;
  learning_path?: string[];
  recommended_resources?: string[];
  expected_outcomes?: string[];
  troubleshooting_tips?: string[];
  knowledge_coverage?: string;
}

function CodeBlock({ code, language = 'python' }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const copyCode = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative bg-dark-200 rounded-lg overflow-hidden">
      <div className="flex justify-between items-center px-4 py-2 bg-dark-300 border-b border-dark-400">
        <span className="text-xs text-gray-500 font-mono">{language}</span>
        <button
          onClick={copyCode}
          className="text-gray-400 hover:text-white transition-colors"
          title="Copy code"
        >
          {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-sm">
        <code className="text-gray-300 font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false
}: {
  title: string;
  icon: any;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-dark-400 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-dark-200 hover:bg-dark-300 transition-colors"
      >
        <div className="flex items-center gap-2 text-gray-300">
          <Icon className="w-4 h-4 text-accent-blue" />
          <span className="font-medium">{title}</span>
        </div>
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
      {open && <div className="p-4 bg-dark-100">{children}</div>}
    </div>
  );
}

function SuggestionCard({ suggestion, onSave }: { suggestion: BuildSuggestion; onSave: () => void }) {
  const [expanded, setExpanded] = useState(false);

  const getFeasibilityColor = (f: string) => {
    switch(f) {
      case 'high': return 'text-green-400 bg-green-500/20';
      case 'medium': return 'text-yellow-400 bg-yellow-500/20';
      case 'low': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getComplexityColor = (c?: string) => {
    switch(c) {
      case 'beginner': return 'text-green-400';
      case 'intermediate': return 'text-yellow-400';
      case 'advanced': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden hover:border-accent-blue/50 transition-colors">
      {/* Header */}
      <div className="p-6 border-b border-dark-300">
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1">
            <h3 className="text-xl font-semibold text-gray-100">{suggestion.title}</h3>
            <p className="text-gray-400 mt-2 leading-relaxed">{suggestion.description}</p>
          </div>
          <button
            onClick={onSave}
            className="p-2 hover:bg-dark-200 rounded-lg transition-colors group"
            title="Save idea"
          >
            <Bookmark className="w-5 h-5 text-gray-500 group-hover:text-accent-blue" />
          </button>
        </div>

        {/* Quick stats */}
        <div className="flex flex-wrap gap-3 mt-4">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${getFeasibilityColor(suggestion.feasibility)}`}>
            <Target className="w-3 h-3 inline mr-1" />
            {suggestion.feasibility} feasibility
          </span>
          <span className="px-3 py-1 rounded-full text-sm font-medium text-blue-400 bg-blue-500/20">
            <Clock className="w-3 h-3 inline mr-1" />
            {suggestion.effort_estimate}
          </span>
          {suggestion.complexity_level && (
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getComplexityColor(suggestion.complexity_level)} bg-dark-200`}>
              <Gauge className="w-3 h-3 inline mr-1" />
              {suggestion.complexity_level}
            </span>
          )}
          {suggestion.knowledge_coverage && (
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getFeasibilityColor(suggestion.knowledge_coverage)}`}>
              <Sparkles className="w-3 h-3 inline mr-1" />
              {suggestion.knowledge_coverage} coverage
            </span>
          )}
        </div>

        {/* Required skills */}
        <div className="mt-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Tech Stack Required</p>
          <div className="flex flex-wrap gap-2">
            {suggestion.required_skills?.map((skill, i) => (
              <span key={i} className="badge badge-primary">{skill}</span>
            ))}
          </div>
        </div>

        {/* Missing knowledge warning */}
        {suggestion.missing_knowledge && suggestion.missing_knowledge.length > 0 && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <p className="text-xs text-yellow-400 uppercase tracking-wide mb-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Knowledge Gaps
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestion.missing_knowledge.map((gap, i) => (
                <span key={i} className="text-sm text-yellow-300">{gap}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Expand button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-3 flex items-center justify-center gap-2 text-accent-blue hover:bg-dark-200 transition-colors"
      >
        {expanded ? (
          <>Hide Details <ChevronDown className="w-4 h-4" /></>
        ) : (
          <>View Full Build Plan <ChevronRight className="w-4 h-4" /></>
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="p-6 space-y-4 border-t border-dark-300 bg-dark-50">
          {/* File Structure */}
          {suggestion.file_structure && (
            <CollapsibleSection title="Project Structure" icon={FolderTree} defaultOpen>
              <CodeBlock code={suggestion.file_structure} language="plaintext" />
            </CollapsibleSection>
          )}

          {/* Starter Code */}
          {suggestion.starter_code && (
            <CollapsibleSection title="Starter Code" icon={Code} defaultOpen>
              <CodeBlock code={suggestion.starter_code} language="python" />
            </CollapsibleSection>
          )}

          {/* Starter Steps */}
          {suggestion.starter_steps && suggestion.starter_steps.length > 0 && (
            <CollapsibleSection title="Step-by-Step Guide" icon={ListChecks} defaultOpen>
              <ol className="space-y-2">
                {suggestion.starter_steps.map((step, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-blue/20 text-accent-blue text-sm flex items-center justify-center font-medium">
                      {i + 1}
                    </span>
                    <span className="text-gray-300 pt-0.5">{step}</span>
                  </li>
                ))}
              </ol>
            </CollapsibleSection>
          )}

          {/* Learning Path */}
          {suggestion.learning_path && suggestion.learning_path.length > 0 && (
            <CollapsibleSection title="Learning Path" icon={BookOpen}>
              <ul className="space-y-2">
                {suggestion.learning_path.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <span className="text-accent-green">→</span>
                    {item}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Expected Outcomes */}
          {suggestion.expected_outcomes && suggestion.expected_outcomes.length > 0 && (
            <CollapsibleSection title="What You'll Achieve" icon={Target}>
              <ul className="space-y-2">
                {suggestion.expected_outcomes.map((outcome, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <Check className="w-4 h-4 text-green-400 mt-1 flex-shrink-0" />
                    {outcome}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Resources */}
          {suggestion.recommended_resources && suggestion.recommended_resources.length > 0 && (
            <CollapsibleSection title="Recommended Resources" icon={ExternalLink}>
              <ul className="space-y-2">
                {suggestion.recommended_resources.map((resource, i) => (
                  <li key={i} className="text-accent-blue hover:underline cursor-pointer flex items-center gap-2">
                    <ExternalLink className="w-3 h-3" />
                    {resource}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Troubleshooting */}
          {suggestion.troubleshooting_tips && suggestion.troubleshooting_tips.length > 0 && (
            <CollapsibleSection title="Troubleshooting Tips" icon={AlertTriangle}>
              <ul className="space-y-2">
                {suggestion.troubleshooting_tips.map((tip, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <AlertTriangle className="w-4 h-4 text-yellow-400 mt-1 flex-shrink-0" />
                    {tip}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  );
}

export default function BuildPage() {
  const [suggestions, setSuggestions] = useState<BuildSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [maxSuggestions, setMaxSuggestions] = useState(5);
  const [knowledgeSummary, setKnowledgeSummary] = useState<any>(null);

  const getSuggestions = async () => {
    setLoading(true);
    try {
      const data = await api.whatCanIBuild(maxSuggestions, true);
      setSuggestions(data.suggestions || []);
      setKnowledgeSummary(data.knowledge_summary);

      if (!data.suggestions || data.suggestions.length === 0) {
        toast('Add more content to your knowledge bank for better suggestions!', { icon: '💡' });
      } else {
        toast.success(`Generated ${data.suggestions.length} build ideas!`);
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to get suggestions');
    }
    finally { setLoading(false); }
  };

  const saveIdea = async (suggestion: BuildSuggestion) => {
    try {
      await api.saveIdea({
        custom_title: suggestion.title,
        custom_description: suggestion.description,
        custom_data: suggestion,
        notes: '',
        status: 'saved'
      });
      toast.success('Idea saved!');
    } catch (err) {
      toast.error('Failed to save idea');
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-accent-blue" />
            Build Ideas
          </h1>
          <p className="text-gray-500 mt-1">
            AI-powered project suggestions with code, structure, and learning paths
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <select
            value={maxSuggestions}
            onChange={(e) => setMaxSuggestions(Number(e.target.value))}
            className="input w-auto"
          >
            <option value={3}>3 ideas</option>
            <option value={5}>5 ideas</option>
            <option value={10}>10 ideas</option>
          </select>
          <button
            onClick={getSuggestions}
            disabled={loading}
            className="btn btn-primary flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Lightbulb className="w-4 h-4" />
            )}
            {loading ? 'Analyzing Knowledge...' : 'Generate Ideas'}
          </button>
        </div>
      </div>

      {/* Knowledge summary */}
      {knowledgeSummary && (
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Knowledge Bank Summary</h3>
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="text-gray-300">
              <strong className="text-accent-blue">{knowledgeSummary.total_docs || 0}</strong> documents
            </span>
            <span className="text-gray-300">
              <strong className="text-accent-green">{knowledgeSummary.total_clusters || 0}</strong> topic clusters
            </span>
            {knowledgeSummary.clusters && (
              <span className="text-gray-500">
                Topics: {knowledgeSummary.clusters.slice(0, 5).map((c: any) => c.name || c).join(', ')}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 ? (
        <div className="space-y-6">
          {suggestions.map((suggestion, i) => (
            <SuggestionCard
              key={i}
              suggestion={suggestion}
              onSave={() => saveIdea(suggestion)}
            />
          ))}
        </div>
      ) : !loading && (
        <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
          <Lightbulb className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300">No build ideas yet</h3>
          <p className="text-gray-500 mt-2 max-w-md mx-auto">
            Click "Generate Ideas" to analyze your knowledge bank and get personalized project suggestions with code, file structures, and step-by-step guides.
          </p>
        </div>
      )}
    </div>
  );
}
