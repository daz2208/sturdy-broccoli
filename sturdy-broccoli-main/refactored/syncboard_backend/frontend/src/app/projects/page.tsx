'use client';

import { useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { FolderKanban, Plus, Play, CheckCircle, XCircle, Clock, Trash2 } from 'lucide-react';
import type { ProjectAttempt, ProjectStats } from '@/types/api';

const STATUS_COLORS = {
  planned: 'text-blue-400 bg-blue-400/10',
  in_progress: 'text-yellow-400 bg-yellow-400/10',
  completed: 'text-green-400 bg-green-400/10',
  abandoned: 'text-red-400 bg-red-400/10',
};

const STATUS_ICONS = {
  planned: Clock,
  in_progress: Play,
  completed: CheckCircle,
  abandoned: XCircle,
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectAttempt[]>([]);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [filter, setFilter] = useState<string>('');

  const loadData = useCallback(async () => {
    try {
      const [projectsData, statsData] = await Promise.all([
        api.getProjects(filter || undefined),
        api.getProjectStats(),
      ]);
      setProjects(Array.isArray(projectsData) ? projectsData : []);
      setStats(statsData);
    } catch {
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createProject = async () => {
    if (!newTitle.trim()) return;
    try {
      await api.createProject(newTitle, newDescription);
      toast.success('Project created');
      setNewTitle('');
      setNewDescription('');
      setShowCreate(false);
      loadData();
    } catch {
      toast.error('Failed to create project');
    }
  };

  const deleteProject = async (id: number) => {
    if (!confirm('Delete this project?')) return;
    try {
      await api.deleteProject(id);
      toast.success('Project deleted');
      loadData();
    } catch {
      toast.error('Failed to delete project');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Projects</h1>
          <p className="text-gray-500">Track your project attempts and progress</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Project
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-gray-500 text-sm">Total</p>
            <p className="text-2xl font-bold text-gray-100">{stats.total_projects}</p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-gray-500 text-sm">Completed</p>
            <p className="text-2xl font-bold text-green-400">{stats.completed}</p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-gray-500 text-sm">In Progress</p>
            <p className="text-2xl font-bold text-yellow-400">{stats.in_progress}</p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-gray-500 text-sm">Completion Rate</p>
            <p className="text-2xl font-bold text-primary">{Math.round(stats.completion_rate)}%</p>
          </div>
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <p className="text-gray-500 text-sm">Total Revenue</p>
            <p className="text-2xl font-bold text-green-400">${stats.total_revenue}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2">
        {['', 'planned', 'in_progress', 'completed', 'abandoned'].map(status => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-3 py-1 rounded-full text-sm ${
              filter === status ? 'bg-primary text-black' : 'bg-dark-200 text-gray-400 hover:text-gray-200'
            }`}
          >
            {status || 'All'}
          </button>
        ))}
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-dark-100 rounded-xl border border-primary p-6">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">Create Project</h3>
          <div className="space-y-4">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Project title"
              className="input w-full"
            />
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Description"
              className="input w-full"
              rows={3}
            />
            <div className="flex gap-2">
              <button onClick={createProject} className="btn btn-primary">Create</button>
              <button onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Projects List */}
      <div className="grid gap-4">
        {projects.map(project => {
          const StatusIcon = STATUS_ICONS[project.status];
          return (
            <div key={project.id} className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <FolderKanban className="w-6 h-6 text-primary mt-1" />
                  <div>
                    <h3 className="text-lg font-semibold text-gray-200">{project.title}</h3>
                    <p className="text-sm text-gray-500 mt-1">{project.description}</p>
                    <div className="flex items-center gap-4 mt-3">
                      <span className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 ${STATUS_COLORS[project.status]}`}>
                        <StatusIcon className="w-3 h-3" /> {project.status.replace('_', ' ')}
                      </span>
                      {project.time_spent_hours && (
                        <span className="text-xs text-gray-400">{project.time_spent_hours}h spent</span>
                      )}
                      {project.revenue_generated && (
                        <span className="text-xs text-green-400">${project.revenue_generated} earned</span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => deleteProject(project.id)}
                  className="text-gray-500 hover:text-red-400"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          );
        })}
        {projects.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No projects found. Create your first project to get started.
          </div>
        )}
      </div>
    </div>
  );
}
