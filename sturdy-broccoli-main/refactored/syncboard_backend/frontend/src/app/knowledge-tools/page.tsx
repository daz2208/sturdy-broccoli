'use client';
import Link from 'next/link';
import { Brain, FileText, Newspaper, Route, Star, MessageCircle, Code, GitCompare, Smile, Mic, Bug } from 'lucide-react';

const tools = [
  { name: 'Gap Analysis', href: '/knowledge-tools/gaps', icon: Brain, description: 'Find gaps in your knowledge', color: 'text-accent-purple' },
  { name: 'Flashcards', href: '/knowledge-tools/flashcards', icon: FileText, description: 'Generate study flashcards', color: 'text-accent-orange' },
  { name: 'Weekly Digest', href: '/knowledge-tools/digest', icon: Newspaper, description: 'Get learning summaries', color: 'text-accent-blue' },
  { name: 'Learning Path', href: '/knowledge-tools/learning-path', icon: Route, description: 'Optimize your learning', color: 'text-accent-green' },
  { name: 'Doc Quality', href: '/knowledge-tools/quality', icon: Star, description: 'Score document quality', color: 'text-yellow-400' },
  { name: 'KB Chat', href: '/knowledge-tools/chat', icon: MessageCircle, description: 'Chat with your KB', color: 'text-primary' },
  { name: 'Code Gen', href: '/knowledge-tools/code-gen', icon: Code, description: 'Generate code from KB', color: 'text-accent-green' },
  { name: 'Compare Docs', href: '/knowledge-tools/compare', icon: GitCompare, description: 'Compare documents', color: 'text-accent-blue' },
  { name: 'ELI5', href: '/knowledge-tools/eli5', icon: Smile, description: 'Simple explanations', color: 'text-accent-orange' },
  { name: 'Interview Prep', href: '/knowledge-tools/interview', icon: Mic, description: 'Practice questions', color: 'text-accent-purple' },
  { name: 'Debug Assistant', href: '/knowledge-tools/debug', icon: Bug, description: 'Debug with KB context', color: 'text-accent-red' },
];

export default function KnowledgeToolsPage() {
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Knowledge Tools</h1>
        <p className="text-gray-500">AI-powered tools to enhance your learning</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tools.map(tool => (
          <Link key={tool.href} href={tool.href} className="bg-dark-100 rounded-xl border border-dark-300 p-6 hover:border-primary/50 transition-colors group">
            <tool.icon className={`w-8 h-8 ${tool.color} mb-3 group-hover:scale-110 transition-transform`} />
            <h3 className="font-semibold text-gray-200">{tool.name}</h3>
            <p className="text-sm text-gray-500 mt-1">{tool.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
