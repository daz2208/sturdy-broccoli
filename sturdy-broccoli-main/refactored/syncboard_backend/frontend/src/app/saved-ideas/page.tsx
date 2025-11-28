'use client';
import { useState, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Bookmark,
  Loader2,
  Trash2,
  Play,
  CheckCircle,
  Clock,
  Code,
  FolderTree,
  ListChecks,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Filter,
  Sparkles,
  Target,
  AlertTriangle,
  ExternalLink,
  Edit3,
  Save,
  X,
  RefreshCw,
  Layers,
  Zap,
  Copy,
  Check,
  Map,
  Download
} from 'lucide-react';

interface SavedIdea {
  id: number;
  idea_seed_id?: number;
  custom_title: string;
  custom_description: string;
  custom_data?: any;
  data?: any; // Additional data field from backend
  title?: string; // Original title from idea seed
  description?: string; // Original description from idea seed
  notes: string;
  status: 'saved' | 'started' | 'completed';
  created_at: string;
  saved_at?: string; // When the idea was saved
}

interface MegaProject {
  title: string;
  description: string;
  value_proposition: string;
  tech_stack: {
    languages: string[];
    frameworks: string[];
    databases: string[];
    tools: string[];
  };
  architecture: string;
  file_structure: string;
  starter_code: string;
  modules: Array<{
    name: string;
    purpose: string;
    files: string[];
    from_idea: string;
  }>;
  implementation_roadmap: Array<{
    phase: number;
    title: string;
    tasks: string[];
    estimated_hours: number;
  }>;
  learning_path: string[];
  complexity_level: string;
  total_effort_estimate: string;
  expected_outcomes: string[];
  potential_extensions: string[];
  source_ideas: Array<{ id: number; title: string }>;
  combined_skills: string[];
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    saved: { icon: Bookmark, color: 'text-blue-400 bg-blue-500/20', label: 'Saved' },
    started: { icon: Play, color: 'text-yellow-400 bg-yellow-500/20', label: 'In Progress' },
    completed: { icon: CheckCircle, color: 'text-green-400 bg-green-500/20', label: 'Completed' }
  }[status] || { icon: Bookmark, color: 'text-gray-400 bg-gray-500/20', label: status };

  const Icon = config.icon;

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1 ${config.color}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

function CodeBlock({ code, language = 'plaintext' }: { code: string; language?: string }) {
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
      <pre className="p-4 overflow-x-auto text-sm max-h-96">
        <code className="text-gray-300 font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

function MegaProjectDisplay({ project, onClose }: { project: MegaProject; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<'overview' | 'structure' | 'code' | 'roadmap'>('overview');

  const totalHours = project.implementation_roadmap?.reduce((sum, p) => sum + (p.estimated_hours || 0), 0) || 0;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-dark-100 rounded-2xl border border-dark-300 max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-dark-300 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Layers className="w-8 h-8 text-accent-purple" />
              <h2 className="text-2xl font-bold text-white">{project.title}</h2>
            </div>
            <p className="text-gray-400">{project.description}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              <span className="px-3 py-1 rounded-full text-sm bg-purple-500/20 text-purple-400">
                {project.complexity_level}
              </span>
              <span className="px-3 py-1 rounded-full text-sm bg-blue-500/20 text-blue-400">
                <Clock className="w-3 h-3 inline mr-1" />
                {project.total_effort_estimate}
              </span>
              <span className="px-3 py-1 rounded-full text-sm bg-green-500/20 text-green-400">
                {project.source_ideas?.length || 0} ideas combined
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-2">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-dark-300">
          {[
            { id: 'overview', label: 'Overview', icon: Sparkles },
            { id: 'structure', label: 'Structure', icon: FolderTree },
            { id: 'code', label: 'Code', icon: Code },
            { id: 'roadmap', label: 'Roadmap', icon: Map }
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-1 px-4 py-3 flex items-center justify-center gap-2 transition-colors ${
                  activeTab === tab.id
                    ? 'bg-dark-200 text-accent-blue border-b-2 border-accent-blue'
                    : 'text-gray-400 hover:text-white hover:bg-dark-200/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Value Proposition */}
              <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-xl p-6 border border-purple-500/30">
                <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-400" />
                  Value Proposition
                </h3>
                <p className="text-gray-300">{project.value_proposition}</p>
              </div>

              {/* Tech Stack */}
              <div className="bg-dark-200 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Tech Stack</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase mb-2">Languages</p>
                    <div className="flex flex-wrap gap-1">
                      {project.tech_stack?.languages?.map((l, i) => (
                        <span key={i} className="badge badge-primary">{l}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase mb-2">Frameworks</p>
                    <div className="flex flex-wrap gap-1">
                      {project.tech_stack?.frameworks?.map((f, i) => (
                        <span key={i} className="badge badge-success">{f}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase mb-2">Databases</p>
                    <div className="flex flex-wrap gap-1">
                      {project.tech_stack?.databases?.map((d, i) => (
                        <span key={i} className="badge badge-purple">{d}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase mb-2">Tools</p>
                    <div className="flex flex-wrap gap-1">
                      {project.tech_stack?.tools?.map((t, i) => (
                        <span key={i} className="badge bg-dark-300 text-gray-300">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Architecture */}
              <div className="bg-dark-200 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-3">Architecture</h3>
                <p className="text-gray-300">{project.architecture}</p>
              </div>

              {/* Modules */}
              {project.modules && project.modules.length > 0 && (
                <div className="bg-dark-200 rounded-xl p-6">
                  <h3 className="text-lg font-semibold text-white mb-4">Modules</h3>
                  <div className="grid gap-3">
                    {project.modules.map((mod, i) => (
                      <div key={i} className="bg-dark-100 rounded-lg p-4 border border-dark-300">
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="font-medium text-white">{mod.name}</h4>
                            <p className="text-sm text-gray-400 mt-1">{mod.purpose}</p>
                          </div>
                          <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-1 rounded">
                            from: {mod.from_idea}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {mod.files?.map((f, j) => (
                            <span key={j} className="text-xs text-gray-500 font-mono bg-dark-300 px-2 py-0.5 rounded">
                              {f}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Expected Outcomes */}
              {project.expected_outcomes && project.expected_outcomes.length > 0 && (
                <div className="bg-dark-200 rounded-xl p-6">
                  <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <Target className="w-5 h-5 text-green-400" />
                    Expected Outcomes
                  </h3>
                  <ul className="space-y-2">
                    {project.expected_outcomes.map((o, i) => (
                      <li key={i} className="flex items-start gap-2 text-gray-300">
                        <CheckCircle className="w-4 h-4 text-green-400 mt-1 flex-shrink-0" />
                        {o}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Learning Path */}
              {project.learning_path && project.learning_path.length > 0 && (
                <div className="bg-dark-200 rounded-xl p-6">
                  <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-blue-400" />
                    Learning Path
                  </h3>
                  <ol className="space-y-2">
                    {project.learning_path.map((item, i) => (
                      <li key={i} className="flex items-start gap-3 text-gray-300">
                        <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-sm flex items-center justify-center flex-shrink-0">
                          {i + 1}
                        </span>
                        {item}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}

          {activeTab === 'structure' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Project Structure</h3>
              {project.file_structure ? (
                <CodeBlock code={project.file_structure} language="plaintext" />
              ) : (
                <p className="text-gray-500">No file structure available</p>
              )}
            </div>
          )}

          {activeTab === 'code' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">Starter Code</h3>
              {project.starter_code ? (
                <CodeBlock code={project.starter_code} language="python" />
              ) : (
                <p className="text-gray-500">No starter code available</p>
              )}
            </div>
          )}

          {activeTab === 'roadmap' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-white">Implementation Roadmap</h3>
                <span className="text-sm text-gray-400">
                  Total: ~{totalHours} hours
                </span>
              </div>
              {project.implementation_roadmap && project.implementation_roadmap.length > 0 ? (
                <div className="space-y-4">
                  {project.implementation_roadmap.map((phase, i) => (
                    <div key={i} className="bg-dark-200 rounded-xl p-6 border-l-4 border-accent-blue">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <span className="text-xs text-accent-blue uppercase tracking-wide">Phase {phase.phase}</span>
                          <h4 className="text-lg font-medium text-white">{phase.title}</h4>
                        </div>
                        <span className="text-sm text-gray-400 bg-dark-300 px-3 py-1 rounded">
                          ~{phase.estimated_hours}h
                        </span>
                      </div>
                      <ul className="space-y-2">
                        {phase.tasks?.map((task, j) => (
                          <li key={j} className="flex items-start gap-2 text-gray-300">
                            <span className="w-5 h-5 rounded border border-dark-400 flex-shrink-0 mt-0.5" />
                            {task}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">No roadmap available</p>
              )}

              {/* Potential Extensions */}
              {project.potential_extensions && project.potential_extensions.length > 0 && (
                <div className="bg-dark-200 rounded-xl p-6 mt-6">
                  <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-yellow-400" />
                    Future Extensions
                  </h3>
                  <ul className="space-y-2">
                    {project.potential_extensions.map((ext, i) => (
                      <li key={i} className="flex items-start gap-2 text-gray-300">
                        <span className="text-yellow-400">+</span>
                        {ext}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function IdeaCard({
  idea,
  onStatusChange,
  onDelete,
  onNotesUpdate,
  selected,
  onToggleSelect
}: {
  idea: SavedIdea;
  onStatusChange: (id: number, status: string) => void;
  onDelete: (id: number) => void;
  onNotesUpdate: (id: number, notes: string) => void;
  selected: boolean;
  onToggleSelect: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState(idea.notes || '');

  const data = idea.data || idea.custom_data || {};

  const saveNotes = () => {
    onNotesUpdate(idea.id, notes);
    setEditingNotes(false);
  };

  const downloadBuildPlan = () => {
    // Generate comprehensive Markdown from saved idea data
    const markdown = `# ${idea.custom_title || idea.title || 'Build Plan'}

## 📋 Overview

**Description:**
${idea.description || idea.custom_description || 'No description available'}

---

## 📊 Project Metrics

| Metric | Value |
|--------|-------|
| **Feasibility** | ${data.feasibility || 'Not specified'} |
| **Effort Estimate** | ${data.effort_estimate || 'Not specified'} |
| **Complexity Level** | ${data.complexity_level || 'intermediate'} |
| **Knowledge Coverage** | ${data.knowledge_coverage || 'Not specified'} |
| **Status** | ${idea.status} |

---

## 🛠️ Tech Stack Required

${data.required_skills?.map((skill: string) => `- ${skill}`).join('\n') || '*No tech stack specified*'}

---

## ❓ Knowledge Gaps

${data.missing_knowledge?.map((gap: string) => `- ${gap}`).join('\n') || '*No knowledge gaps identified*'}

---

## 📁 Project Structure

\`\`\`
${data.file_structure || '*No project structure available*'}
\`\`\`

---

## 🚀 Step-by-Step Guide

${data.starter_steps?.map((step: string, i: number) => `${i + 1}. ${step}`).join('\n') || '*No step-by-step guide available*'}

---

## 💻 Starter Code

${data.starter_code ? `\`\`\`python\n${data.starter_code}\n\`\`\`` : '*Starter code will be generated when you begin this project*'}

---

## 📚 Learning Path

Follow these phases to build this project successfully:

${data.learning_path?.map((item: string, i: number) => `${i + 1}. ${item}`).join('\n') || `1. **Setup & Foundation** - Environment setup, dependencies, basic structure
2. **Core Implementation** - Build the main features
3. **Testing & Validation** - Ensure everything works correctly
4. **Deployment & Polish** - Deploy and refine the project
5. **Documentation** - Document your learnings and the project`}

---

## 🎯 What You'll Achieve

By completing this project, you will:

${data.expected_outcomes?.map((outcome: string) => `- ✅ ${outcome}`).join('\n') || `- ✅ Build a production-ready ${(idea.custom_title || idea.title || 'project').toLowerCase()}
- ✅ Master the required tech stack
- ✅ Fill your identified knowledge gaps
- ✅ Create a portfolio-worthy project
- ✅ Gain practical experience with real-world patterns`}

---

## 📖 Recommended Resources

${data.recommended_resources?.map((resource: string) => `- ${resource}`).join('\n') || `### Documentation
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

${data.troubleshooting_tips?.map((tip: string) => `- ${tip}`).join('\n') || `### Common Issues

**Environment Setup Issues**
- Ensure all dependencies are installed correctly
- Check version compatibility
- Use virtual environments to avoid conflicts

**Implementation Challenges**
- Start with the simplest working version
- Test each component independently
- Use logging to debug issues`}

---

## 📝 Your Notes

${idea.notes || '*No notes yet*'}

---

**Created:** ${new Date(idea.saved_at || idea.created_at).toLocaleDateString()}
**Status:** ${idea.status === 'saved' ? '📌 Saved' : idea.status === 'started' ? '🔄 In Progress' : '✅ Completed'}

---

*Generated by SyncBoard 3.0 Build Ideas System*
`;

    // Create download
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeTitle = (idea.custom_title || idea.title || 'build-plan').replace(/[^a-z0-9]/gi, ' ').trim();
    link.download = `${safeTitle} - Build Plan.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    toast.success('Build plan downloaded');
  };

  return (
    <div className={`bg-dark-100 rounded-xl border overflow-hidden transition-colors ${
      selected ? 'border-accent-purple ring-2 ring-accent-purple/30' : 'border-dark-300'
    }`}>
      {/* Header */}
      <div className="p-6">
        <div className="flex justify-between items-start gap-4">
          <div className="flex items-start gap-3">
            {/* Selection checkbox */}
            <button
              onClick={() => onToggleSelect(idea.id)}
              className={`mt-1 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                selected
                  ? 'bg-accent-purple border-accent-purple text-white'
                  : 'border-dark-400 hover:border-accent-purple'
              }`}
            >
              {selected && <Check className="w-3 h-3" />}
            </button>

            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <StatusBadge status={idea.status} />
                <span className="text-xs text-gray-500">
                  <Clock className="w-3 h-3 inline mr-1" />
                  {new Date(idea.saved_at || idea.created_at).toLocaleDateString()}
                </span>
              </div>
              <h3 className="text-xl font-semibold text-gray-100">{idea.custom_title || idea.title || 'Saved Idea'}</h3>
              <p className="text-gray-400 mt-2">{idea.description || idea.custom_description || 'No description'}</p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {idea.status === 'saved' && (
              <button
                onClick={() => onStatusChange(idea.id, 'started')}
                className="btn btn-sm bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30"
                title="Start working on this"
              >
                <Play className="w-4 h-4" />
              </button>
            )}
            {idea.status === 'started' && (
              <button
                onClick={() => onStatusChange(idea.id, 'completed')}
                className="btn btn-sm bg-green-500/20 text-green-400 hover:bg-green-500/30"
                title="Mark as completed"
              >
                <CheckCircle className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={downloadBuildPlan}
              className="btn btn-sm bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
              title="Download full build plan"
            >
              <Download className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(idea.id)}
              className="btn btn-sm bg-red-500/20 text-red-400 hover:bg-red-500/30"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Quick stats from saved data */}
        {data.required_skills && (
          <div className="mt-4 ml-8">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Tech Stack</p>
            <div className="flex flex-wrap gap-2">
              {data.required_skills.map((skill: string, i: number) => (
                <span key={i} className="badge badge-primary">{skill}</span>
              ))}
            </div>
          </div>
        )}

        {/* Quick info */}
        <div className="flex flex-wrap gap-3 mt-4 ml-8">
          {data.effort_estimate && (
            <span className="px-3 py-1 rounded-full text-sm text-blue-400 bg-blue-500/20">
              <Clock className="w-3 h-3 inline mr-1" />
              {data.effort_estimate}
            </span>
          )}
          {data.complexity_level && (
            <span className="px-3 py-1 rounded-full text-sm text-purple-400 bg-purple-500/20">
              {data.complexity_level}
            </span>
          )}
          {data.feasibility && (
            <span className={`px-3 py-1 rounded-full text-sm ${
              data.feasibility === 'high' ? 'text-green-400 bg-green-500/20' :
              data.feasibility === 'medium' ? 'text-yellow-400 bg-yellow-500/20' :
              'text-red-400 bg-red-500/20'
            }`}>
              <Target className="w-3 h-3 inline mr-1" />
              {data.feasibility} feasibility
            </span>
          )}
        </div>

        {/* Notes section */}
        <div className="mt-4 ml-8 p-3 bg-dark-200 rounded-lg">
          <div className="flex justify-between items-center mb-2">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Your Notes</p>
            {!editingNotes ? (
              <button
                onClick={() => setEditingNotes(true)}
                className="text-gray-400 hover:text-white"
              >
                <Edit3 className="w-4 h-4" />
              </button>
            ) : (
              <div className="flex gap-2">
                <button onClick={saveNotes} className="text-green-400 hover:text-green-300">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => { setEditingNotes(false); setNotes(idea.notes || ''); }} className="text-red-400 hover:text-red-300">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
          {editingNotes ? (
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-dark-300 border border-dark-400 rounded p-2 text-gray-300 text-sm"
              rows={3}
              placeholder="Add your notes, progress, ideas..."
            />
          ) : (
            <p className="text-gray-400 text-sm">
              {idea.notes || 'No notes yet. Click edit to add some.'}
            </p>
          )}
        </div>
      </div>

      {/* Expand for full details */}
      {data.starter_code || data.file_structure || data.starter_steps ? (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-6 py-3 flex items-center justify-center gap-2 text-accent-blue hover:bg-dark-200 transition-colors border-t border-dark-300"
          >
            {expanded ? (
              <>Hide Build Plan <ChevronDown className="w-4 h-4" /></>
            ) : (
              <>View Build Plan <ChevronRight className="w-4 h-4" /></>
            )}
          </button>

          {expanded && (
            <div className="p-6 space-y-4 border-t border-dark-300 bg-dark-50">
              {/* File Structure */}
              {data.file_structure && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <FolderTree className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Project Structure</span>
                  </div>
                  <pre className="p-4 bg-dark-100 overflow-x-auto text-sm">
                    <code className="text-gray-300 font-mono whitespace-pre">{data.file_structure}</code>
                  </pre>
                </div>
              )}

              {/* Starter Code */}
              {data.starter_code && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <Code className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Starter Code</span>
                  </div>
                  <pre className="p-4 bg-dark-100 overflow-x-auto text-sm">
                    <code className="text-gray-300 font-mono whitespace-pre">{data.starter_code}</code>
                  </pre>
                </div>
              )}

              {/* Starter Steps */}
              {data.starter_steps && data.starter_steps.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <ListChecks className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Step-by-Step Guide</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ol className="space-y-2">
                      {data.starter_steps.map((step: string, i: number) => (
                        <li key={i} className="flex items-start gap-3">
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-blue/20 text-accent-blue text-sm flex items-center justify-center font-medium">
                            {i + 1}
                          </span>
                          <span className="text-gray-300 pt-0.5">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}

              {/* Learning Path */}
              {data.learning_path && data.learning_path.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <BookOpen className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Learning Path</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ul className="space-y-2">
                      {data.learning_path.map((item: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-gray-300">
                          <span className="text-accent-green">→</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Resources */}
              {data.recommended_resources && data.recommended_resources.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <ExternalLink className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Resources</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ul className="space-y-2">
                      {data.recommended_resources.map((resource: string, i: number) => (
                        <li key={i} className="text-accent-blue hover:underline cursor-pointer flex items-center gap-2">
                          <ExternalLink className="w-3 h-3" />
                          {resource}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

export default function SavedIdeasPage() {
  const [ideas, setIdeas] = useState<SavedIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [megaProject, setMegaProject] = useState<MegaProject | null>(null);
  const [generatingMega, setGeneratingMega] = useState(false);

  const loadIdeas = async () => {
    setLoading(true);
    try {
      const status = filter === 'all' ? undefined : filter;
      const data = await api.getSavedIdeas(status, 100);
      setIdeas(data.saved_ideas || []);
    } catch (err) {
      toast.error('Failed to load saved ideas');
    }
    setLoading(false);
  };

  useEffect(() => {
    loadIdeas();
  }, [filter]);

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await api.updateSavedIdea(id, { status });
      toast.success(`Status updated to ${status}`);
      loadIdeas();
    } catch (err) {
      toast.error('Failed to update status');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this idea?')) return;
    try {
      await api.deleteSavedIdea(id);
      toast.success('Idea deleted');
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      loadIdeas();
    } catch (err) {
      toast.error('Failed to delete idea');
    }
  };

  const handleNotesUpdate = async (id: number, notes: string) => {
    try {
      await api.updateSavedIdea(id, { notes });
      toast.success('Notes saved');
      loadIdeas();
    } catch (err) {
      toast.error('Failed to save notes');
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === ideas.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ideas.map(i => i.id)));
    }
  };

  const createMegaProject = async () => {
    if (selectedIds.size < 2) {
      toast.error('Select at least 2 ideas to combine');
      return;
    }

    setGeneratingMega(true);
    try {
      const result = await api.createMegaProject(Array.from(selectedIds));
      setMegaProject(result.mega_project);
      toast.success('Mega-project created!');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create mega-project');
    }
    setGeneratingMega(false);
  };

  const stats = {
    total: ideas.length,
    saved: ideas.filter(i => i.status === 'saved').length,
    started: ideas.filter(i => i.status === 'started').length,
    completed: ideas.filter(i => i.status === 'completed').length
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Mega-project modal */}
      {megaProject && (
        <MegaProjectDisplay project={megaProject} onClose={() => setMegaProject(null)} />
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Bookmark className="w-6 h-6 text-accent-blue" />
            Saved Ideas
          </h1>
          <p className="text-gray-500 mt-1">
            Manage your bookmarked build ideas and track progress
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <button
            onClick={loadIdeas}
            className="btn btn-ghost"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Ideas ({stats.total})</option>
            <option value="saved">Saved ({stats.saved})</option>
            <option value="started">In Progress ({stats.started})</option>
            <option value="completed">Completed ({stats.completed})</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Total Ideas</p>
          <p className="text-2xl font-bold text-white">{stats.total}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-blue-400 text-sm flex items-center gap-1">
            <Bookmark className="w-3 h-3" /> Saved
          </p>
          <p className="text-2xl font-bold text-white">{stats.saved}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-yellow-400 text-sm flex items-center gap-1">
            <Play className="w-3 h-3" /> In Progress
          </p>
          <p className="text-2xl font-bold text-white">{stats.started}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-green-400 text-sm flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> Completed
          </p>
          <p className="text-2xl font-bold text-white">{stats.completed}</p>
        </div>
      </div>

      {/* Mega-Project Builder */}
      {ideas.length >= 2 && (
        <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-xl border border-purple-500/30 p-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-accent-purple" />
                Mega-Project Builder
              </h2>
              <p className="text-gray-400 text-sm mt-1">
                Select 2 or more ideas to combine them into a unified mega-project
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={selectAll}
                className="btn btn-ghost text-sm"
              >
                {selectedIds.size === ideas.length ? 'Deselect All' : 'Select All'}
              </button>
              <button
                onClick={createMegaProject}
                disabled={selectedIds.size < 2 || generatingMega}
                className={`btn flex items-center gap-2 ${
                  selectedIds.size >= 2
                    ? 'bg-accent-purple text-white hover:bg-accent-purple/80'
                    : 'bg-dark-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                {generatingMega ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Create Mega-Project ({selectedIds.size} selected)
                  </>
                )}
              </button>
            </div>
          </div>
          {selectedIds.size > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {ideas.filter(i => selectedIds.has(i.id)).map(idea => (
                <span
                  key={idea.id}
                  className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm flex items-center gap-2"
                >
                  {idea.custom_title || idea.title || 'Saved Idea'}
                  <button
                    onClick={() => toggleSelect(idea.id)}
                    className="hover:text-white"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Ideas list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
        </div>
      ) : ideas.length > 0 ? (
        <div className="space-y-6">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              onStatusChange={handleStatusChange}
              onDelete={handleDelete}
              onNotesUpdate={handleNotesUpdate}
              selected={selectedIds.has(idea.id)}
              onToggleSelect={toggleSelect}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
          <Bookmark className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300">No saved ideas yet</h3>
          <p className="text-gray-500 mt-2 max-w-md mx-auto">
            Go to <a href="/build" className="text-accent-blue hover:underline">Build Ideas</a> to generate project suggestions and save the ones you like.
          </p>
        </div>
      )}
    </div>
  );
}
