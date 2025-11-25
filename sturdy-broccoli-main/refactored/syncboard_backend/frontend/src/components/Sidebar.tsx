'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home, Search, FileText, FolderOpen, BarChart3, Lightbulb,
  Cloud, Database, Brain, Target, Workflow, Code, Settings,
  LogOut, ChevronDown, ChevronRight, CheckCircle
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useState } from 'react';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: { name: string; href: string }[];
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: Home },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Clusters', href: '/clusters', icon: FolderOpen },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'AI Validation', href: '/ai-validation', icon: CheckCircle },
  { name: 'Build Ideas', href: '/build', icon: Lightbulb },
  { name: 'Integrations', href: '/integrations', icon: Cloud },
  { name: 'Knowledge Bases', href: '/knowledge-bases', icon: Database },
  {
    name: 'Knowledge Tools',
    href: '/knowledge-tools',
    icon: Brain,
    children: [
      { name: 'Gap Analysis', href: '/knowledge-tools/gaps' },
      { name: 'Flashcards', href: '/knowledge-tools/flashcards' },
      { name: 'Weekly Digest', href: '/knowledge-tools/digest' },
      { name: 'Learning Path', href: '/knowledge-tools/learning-path' },
      { name: 'Doc Quality', href: '/knowledge-tools/quality' },
      { name: 'KB Chat', href: '/knowledge-tools/chat' },
      { name: 'Code Gen', href: '/knowledge-tools/code-gen' },
      { name: 'Compare Docs', href: '/knowledge-tools/compare' },
      { name: 'ELI5', href: '/knowledge-tools/eli5' },
      { name: 'Interview Prep', href: '/knowledge-tools/interview' },
      { name: 'Debug Assistant', href: '/knowledge-tools/debug' },
    ],
  },
  { name: 'Projects', href: '/projects', icon: Target },
  { name: 'Workflows', href: '/workflows', icon: Workflow },
  { name: 'Generated Code', href: '/generated-code', icon: Code },
  { name: 'Admin', href: '/admin', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { logout, username } = useAuthStore();
  const [expandedItems, setExpandedItems] = useState<string[]>(['Knowledge Tools']);

  const toggleExpanded = (name: string) => {
    setExpandedItems(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/');

  return (
    <div className="flex flex-col w-64 bg-dark-100 border-r border-dark-300 h-screen fixed">
      {/* Logo */}
      <div className="p-4 border-b border-dark-300">
        <h1 className="text-xl font-bold text-primary">SyncBoard 3.0</h1>
        <p className="text-xs text-gray-500">Knowledge Management</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        {navigation.map((item) => (
          <div key={item.name}>
            {item.children ? (
              <>
                <button
                  onClick={() => toggleExpanded(item.name)}
                  className={`w-full flex items-center justify-between px-4 py-2 text-sm transition-colors ${
                    isActive(item.href)
                      ? 'text-primary bg-dark-200'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <item.icon className="w-5 h-5" />
                    {item.name}
                  </div>
                  {expandedItems.includes(item.name) ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </button>
                {expandedItems.includes(item.name) && (
                  <div className="ml-8 border-l border-dark-300">
                    {item.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={`block px-4 py-2 text-sm transition-colors ${
                          pathname === child.href
                            ? 'text-primary bg-dark-200'
                            : 'text-gray-500 hover:text-gray-300 hover:bg-dark-200'
                        }`}
                      >
                        {child.name}
                      </Link>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <Link
                href={item.href}
                className={`flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                  isActive(item.href)
                    ? 'text-primary bg-dark-200 border-r-2 border-primary'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-dark-200'
                }`}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            )}
          </div>
        ))}
      </nav>

      {/* User section */}
      <div className="p-4 border-t border-dark-300">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-200">{username}</p>
            <p className="text-xs text-gray-500">Logged in</p>
          </div>
          <button
            onClick={logout}
            className="p-2 text-gray-400 hover:text-accent-red transition-colors"
            title="Logout"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
