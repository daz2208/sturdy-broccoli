'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Workflow, Plus, Download, Trash2, Copy, Loader2 } from 'lucide-react';
import type { N8NWorkflow } from '@/types/api';

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<N8NWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [taskDescription, setTaskDescription] = useState('');

  useEffect(() => { loadWorkflows(); }, []);

  const loadWorkflows = async () => {
    try {
      const data = await api.getN8NWorkflows();
      setWorkflows(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Failed to load workflows');
    } finally {
      setLoading(false);
    }
  };

  const generateWorkflow = async () => {
    if (!taskDescription.trim()) return;
    setGenerating(true);
    try {
      const result = await api.generateN8NWorkflow(taskDescription);
      toast.success('Workflow generated!');
      setTaskDescription('');
      setShowCreate(false);
      loadWorkflows();
    } catch {
      toast.error('Failed to generate workflow');
    } finally {
      setGenerating(false);
    }
  };

  const downloadWorkflow = (id: number) => {
    window.open(api.getN8NWorkflowDownloadUrl(id), '_blank');
  };

  const deleteWorkflow = async (id: number) => {
    if (!confirm('Delete this workflow?')) return;
    try {
      await api.deleteN8NWorkflow(id);
      toast.success('Workflow deleted');
      loadWorkflows();
    } catch {
      toast.error('Failed to delete workflow');
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
          <h1 className="text-2xl font-bold text-gray-100">Workflows</h1>
          <p className="text-gray-500">AI-generated n8n automation workflows</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Generate Workflow
        </button>
      </div>

      {/* Generate Form */}
      {showCreate && (
        <div className="bg-dark-100 rounded-xl border border-primary p-6">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">Generate n8n Workflow</h3>
          <p className="text-sm text-gray-500 mb-4">
            Describe what you want to automate and AI will generate an n8n workflow for you.
          </p>
          <div className="space-y-4">
            <textarea
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              placeholder="E.g., When a new email arrives with an attachment, save it to Google Drive and notify me on Slack"
              className="input w-full"
              rows={4}
            />
            <div className="flex gap-2">
              <button
                onClick={generateWorkflow}
                disabled={generating}
                className="btn btn-primary flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Workflow className="w-4 h-4" />}
                {generating ? 'Generating...' : 'Generate'}
              </button>
              <button onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Workflows List */}
      <div className="grid gap-4">
        {workflows.map(workflow => (
          <div key={workflow.id} className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <Workflow className="w-6 h-6 text-primary mt-1" />
                <div>
                  <h3 className="text-lg font-semibold text-gray-200">{workflow.title}</h3>
                  <p className="text-sm text-gray-500 mt-1">{workflow.description}</p>
                  <div className="flex items-center gap-4 mt-3">
                    {workflow.trigger_type && (
                      <span className="text-xs bg-dark-200 px-2 py-1 rounded text-gray-400">
                        Trigger: {workflow.trigger_type}
                      </span>
                    )}
                    {workflow.estimated_complexity && (
                      <span className="text-xs bg-dark-200 px-2 py-1 rounded text-gray-400">
                        Complexity: {workflow.estimated_complexity}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadWorkflow(workflow.id)}
                  className="btn btn-secondary text-sm"
                  title="Download JSON"
                >
                  <Download className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteWorkflow(workflow.id)}
                  className="btn btn-secondary text-sm text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
        {workflows.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Workflow className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No workflows yet. Generate your first automation workflow!</p>
          </div>
        )}
      </div>
    </div>
  );
}
