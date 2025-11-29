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
  Sparkles,
  Download,
  Zap,
  TrendingUp,
  DollarSign,
  Users,
  CheckCircle,
  XCircle
} from 'lucide-react';
import { BuildSuggestion, QuickIdea, MarketValidationRequest } from '@/types/api';

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

  const downloadBuildPlan = () => {
    const markdown = `# ${suggestion.title}

## 📋 Overview

**Description:**
${suggestion.description}

---

## 📊 Project Metrics

| Metric | Value |
|--------|-------|
| **Feasibility** | ${suggestion.feasibility || 'Not specified'} |
| **Effort Estimate** | ${suggestion.effort_estimate || 'Not specified'} |
| **Complexity Level** | ${suggestion.complexity_level || 'intermediate'} |
| **Knowledge Coverage** | ${suggestion.knowledge_coverage || 'Not specified'} |

---

## 🛠️ Tech Stack Required

${suggestion.required_skills?.map(skill => `- ${skill}`).join('\n') || '*No tech stack specified*'}

---

## ❓ Knowledge Gaps

${suggestion.missing_knowledge?.map(gap => `- ${gap}`).join('\n') || '*No knowledge gaps identified*'}

---

## 📁 Project Structure

\`\`\`
${suggestion.file_structure || '*No project structure available*'}
\`\`\`

---

## 🚀 Step-by-Step Guide

${suggestion.starter_steps?.map((step, i) => `${i + 1}. ${step}`).join('\n') || '*No step-by-step guide available*'}

---

## 💻 Starter Code

${suggestion.starter_code ? `\`\`\`python\n${suggestion.starter_code}\n\`\`\`` : '*Starter code will be generated when you begin this project*'}

---

## 📚 Learning Path

Follow these phases to build this project successfully:

${suggestion.learning_path?.map((item, i) => `${i + 1}. ${item}`).join('\n') || `1. **Setup & Foundation** - Environment setup, dependencies, basic structure
2. **Core Implementation** - Build the main features
3. **Testing & Validation** - Ensure everything works correctly
4. **Deployment & Polish** - Deploy and refine the project
5. **Documentation** - Document your learnings and the project`}

---

## 🎯 What You'll Achieve

By completing this project, you will:

${suggestion.expected_outcomes?.map(outcome => `- ✅ ${outcome}`).join('\n') || `- ✅ Build a production-ready ${suggestion.title.toLowerCase()}
- ✅ Master the required tech stack
- ✅ Fill your identified knowledge gaps
- ✅ Create a portfolio-worthy project
- ✅ Gain practical experience with real-world patterns`}

---

## 📖 Recommended Resources

${suggestion.recommended_resources?.map(resource => `- ${resource}`).join('\n') || `### Documentation
- Official documentation for each tech in your stack
- API references and guides

### Tutorials
- Video walkthroughs for similar projects
- Written tutorials and blog posts

### Community
- Stack Overflow for troubleshooting
- GitHub repositories with similar implementations`}

---

## 🔧 Troubleshooting Tips

${suggestion.troubleshooting_tips?.map(tip => `- ${tip}`).join('\n') || `### Common Issues

**Environment Setup Issues**
- Ensure all dependencies are installed correctly
- Check version compatibility
- Use virtual environments to avoid conflicts

**Implementation Challenges**
- Start with the simplest working version
- Test each component independently
- Use logging to debug issues`}

---

*Generated by SyncBoard 3.0 Build Ideas System*
`;

    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeTitle = suggestion.title.replace(/[^a-z0-9]/gi, ' ').trim();
    link.download = `${safeTitle} - Build Plan.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    toast.success('Build plan downloaded');
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
          <div className="flex gap-2">
            <button
              onClick={downloadBuildPlan}
              className="p-2 hover:bg-dark-200 rounded-lg transition-colors group"
              title="Download full build plan"
            >
              <Download className="w-5 h-5 text-gray-500 group-hover:text-accent-green" />
            </button>
            <button
              onClick={onSave}
              className="p-2 hover:bg-dark-200 rounded-lg transition-colors group"
              title="Save idea"
            >
              <Bookmark className="w-5 h-5 text-gray-500 group-hover:text-accent-blue" />
            </button>
          </div>
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
  const [activeTab, setActiveTab] = useState<'ai' | 'quick' | 'validate'>('quick');
  const [suggestions, setSuggestions] = useState<BuildSuggestion[]>([]);
  const [quickIdeas, setQuickIdeas] = useState<QuickIdea[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingQuick, setLoadingQuick] = useState(false);
  const [validating, setValidating] = useState(false);
  const [maxSuggestions, setMaxSuggestions] = useState(5);
  const [knowledgeSummary, setKnowledgeSummary] = useState<any>(null);
  const [validationResult, setValidationResult] = useState<any>(null);

  // Market validation form
  const [projectTitle, setProjectTitle] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [targetMarket, setTargetMarket] = useState('');

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

  const getQuickIdeas = async (difficulty?: string) => {
    setLoadingQuick(true);
    try {
      const data = await api.getQuickIdeas(difficulty, 10);
      setQuickIdeas(data.ideas);
      if (data.ideas.length === 0) {
        toast('No quick ideas available yet. Upload documents to generate idea seeds!', { icon: '💡' });
      } else {
        toast.success(`Found ${data.ideas.length} instant project ideas!`);
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to load quick ideas');
    } finally {
      setLoadingQuick(false);
    }
  };

  const validateMarket = async () => {
    if (!projectTitle || !projectDescription) {
      toast.error('Please provide project title and description');
      return;
    }

    setValidating(true);
    try {
      const result = await api.validateMarket({
        project_title: projectTitle,
        project_description: projectDescription,
        target_market: targetMarket || undefined,
      });
      setValidationResult(result);
      toast.success('Market validation complete!');
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Market validation failed';
      toast.error(errorMsg);
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-accent-blue" />
          Build Ideas
        </h1>
        <p className="text-gray-500 mt-1">
          Instant project ideas, AI-powered suggestions, and market validation
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-dark-300">
        <button
          onClick={() => setActiveTab('quick')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'quick'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Zap className="w-4 h-4 inline mr-2" />
          Quick Ideas
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'ai'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Sparkles className="w-4 h-4 inline mr-2" />
          AI Build Ideas
        </button>
        <button
          onClick={() => setActiveTab('validate')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'validate'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <TrendingUp className="w-4 h-4 inline mr-2" />
          Market Validation
        </button>
      </div>

      {/* Quick Ideas Tab */}
      {activeTab === 'quick' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-gray-400">
              Instant project ideas from pre-computed seeds (no AI wait time)
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => getQuickIdeas(undefined)}
                disabled={loadingQuick}
                className="btn btn-secondary flex items-center gap-2"
              >
                {loadingQuick ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                All
              </button>
              <button
                onClick={() => getQuickIdeas('easy')}
                disabled={loadingQuick}
                className="btn btn-secondary flex items-center gap-2"
              >
                Easy
              </button>
              <button
                onClick={() => getQuickIdeas('medium')}
                disabled={loadingQuick}
                className="btn btn-secondary flex items-center gap-2"
              >
                Medium
              </button>
              <button
                onClick={() => getQuickIdeas('hard')}
                disabled={loadingQuick}
                className="btn btn-secondary flex items-center gap-2"
              >
                Hard
              </button>
            </div>
          </div>

          {quickIdeas.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {quickIdeas.map((idea) => (
                <div key={idea.id} className="bg-dark-100 rounded-xl border border-dark-300 p-6 hover:border-primary/50 transition-colors">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <h3 className="text-lg font-semibold text-gray-100">{idea.title}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      idea.difficulty === 'easy' ? 'bg-green-500/20 text-green-400' :
                      idea.difficulty === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {idea.difficulty}
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm mb-4">{idea.description}</p>

                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">Time Estimate</p>
                      <p className="text-sm text-gray-300 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {idea.estimated_time}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">Required Skills</p>
                      <div className="flex flex-wrap gap-1">
                        {idea.required_skills.map((skill, idx) => (
                          <span key={idx} className="px-2 py-1 bg-dark-200 rounded text-xs text-gray-400">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>

                    {idea.learning_outcomes.length > 0 && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">You'll Learn</p>
                        <ul className="space-y-1">
                          {idea.learning_outcomes.slice(0, 3).map((outcome, idx) => (
                            <li key={idx} className="text-xs text-gray-400 flex items-start gap-1">
                              <CheckCircle className="w-3 h-3 mt-0.5 flex-shrink-0 text-green-400" />
                              {outcome}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : !loadingQuick && (
            <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
              <Zap className="w-12 h-12 mx-auto text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-300">No quick ideas yet</h3>
              <p className="text-gray-500 mt-2 max-w-md mx-auto">
                Upload documents to automatically generate quick project ideas. Click any difficulty button to load ideas.
              </p>
            </div>
          )}
        </div>
      )}

      {/* AI Build Ideas Tab */}
      {activeTab === 'ai' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-gray-400">
              Deep AI analysis with code, structure, and learning paths
            </p>
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
      )}

      {/* Market Validation Tab */}
      {activeTab === 'validate' && (
        <div className="space-y-6">
          <p className="text-gray-400">
            Validate project ideas against market demand and competition using AI analysis
          </p>

          {/* Input Form */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h3 className="text-lg font-semibold text-gray-200 mb-4">Project Details</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Project Title *</label>
                <input
                  type="text"
                  value={projectTitle}
                  onChange={(e) => setProjectTitle(e.target.value)}
                  placeholder="e.g., AI-Powered Recipe Generator"
                  className="input w-full"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Project Description *</label>
                <textarea
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Describe what your project does, key features, and target users..."
                  className="input w-full h-32 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Target Market (Optional)</label>
                <input
                  type="text"
                  value={targetMarket}
                  onChange={(e) => setTargetMarket(e.target.value)}
                  placeholder="e.g., Home cooks, Food bloggers"
                  className="input w-full"
                />
              </div>

              <button
                onClick={validateMarket}
                disabled={validating || !projectTitle || !projectDescription}
                className="btn btn-primary flex items-center gap-2"
              >
                {validating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <TrendingUp className="w-4 h-4" />
                )}
                {validating ? 'Analyzing Market...' : 'Validate Market'}
              </button>
            </div>
          </div>

          {/* Validation Results */}
          {validationResult && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h3 className="text-xl font-semibold text-gray-200 mb-6">Market Analysis Results</h3>

              {/* Overall Verdict */}
              <div className={`p-4 rounded-lg mb-6 ${
                validationResult.verdict === 'promising' ? 'bg-green-900/20 border border-green-700/50' :
                validationResult.verdict === 'moderate' ? 'bg-yellow-900/20 border border-yellow-700/50' :
                'bg-red-900/20 border border-red-700/50'
              }`}>
                <div className="flex items-center gap-3 mb-2">
                  {validationResult.verdict === 'promising' ? (
                    <CheckCircle className="w-6 h-6 text-green-400" />
                  ) : validationResult.verdict === 'moderate' ? (
                    <AlertCircle className="w-6 h-6 text-yellow-400" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-400" />
                  )}
                  <h4 className={`text-lg font-semibold capitalize ${
                    validationResult.verdict === 'promising' ? 'text-green-300' :
                    validationResult.verdict === 'moderate' ? 'text-yellow-300' :
                    'text-red-300'
                  }`}>
                    {validationResult.verdict} Opportunity
                  </h4>
                </div>
                <p className="text-sm text-gray-300">{validationResult.summary}</p>
              </div>

              {/* Scores */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-dark-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Users className="w-4 h-4 text-blue-400" />
                    <p className="text-sm text-gray-400">Market Demand</p>
                  </div>
                  <p className="text-2xl font-bold text-blue-400">{validationResult.market_demand_score}/10</p>
                </div>

                <div className="bg-dark-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4 text-yellow-400" />
                    <p className="text-sm text-gray-400">Competition Level</p>
                  </div>
                  <p className="text-2xl font-bold text-yellow-400">{validationResult.competition_score}/10</p>
                </div>

                <div className="bg-dark-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <DollarSign className="w-4 h-4 text-green-400" />
                    <p className="text-sm text-gray-400">Viability Score</p>
                  </div>
                  <p className="text-2xl font-bold text-green-400">{validationResult.viability_score}/10</p>
                </div>
              </div>

              {/* Strengths & Risks */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <h4 className="text-sm font-semibold text-green-400 mb-2 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" />
                    Strengths
                  </h4>
                  <ul className="space-y-1">
                    {validationResult.strengths.map((strength: string, idx: number) => (
                      <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                        <span className="text-green-400 mt-1">•</span>
                        {strength}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-red-400 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Risks
                  </h4>
                  <ul className="space-y-1">
                    {validationResult.risks.map((risk: string, idx: number) => (
                      <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                        <span className="text-red-400 mt-1">•</span>
                        {risk}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Recommendations */}
              <div>
                <h4 className="text-sm font-semibold text-primary mb-2 flex items-center gap-2">
                  <Lightbulb className="w-4 h-4" />
                  Recommendations
                </h4>
                <ul className="space-y-2">
                  {validationResult.recommendations.map((rec: string, idx: number) => (
                    <li key={idx} className="text-sm text-gray-300 flex items-start gap-2 bg-dark-200 p-3 rounded">
                      <span className="text-primary mt-1">→</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
