'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Database, Plus, Trash2, Star, Edit2, Check, X } from 'lucide-react';
import type { KnowledgeBase } from '@/types/api';

export default function KnowledgeBasesPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  useEffect(() => { loadKnowledgeBases(); }, []);

  const loadKnowledgeBases = async () => {
    try {
      const data = await api.getKnowledgeBases();
      setKnowledgeBases(data.knowledge_bases);
    } catch {
      toast.error('Failed to load knowledge bases');
    } finally {
      setLoading(false);
    }
  };

  const createKnowledgeBase = async () => {
    if (!newName.trim()) return;
    try {
      await api.createKnowledgeBase(newName, newDescription);
      toast.success('Knowledge base created');
      setNewName('');
      setNewDescription('');
      setShowCreate(false);
      loadKnowledgeBases();
    } catch {
      toast.error('Failed to create knowledge base');
    }
  };

  const deleteKnowledgeBase = async (id: number) => {
    if (!confirm('Are you sure you want to delete this knowledge base?')) return;
    try {
      await api.deleteKnowledgeBase(id);
      toast.success('Knowledge base deleted');
      loadKnowledgeBases();
    } catch {
      toast.error('Failed to delete knowledge base');
    }
  };

  const setDefault = async (id: number) => {
    try {
      await api.updateKnowledgeBase(id, { is_default: true });
      toast.success('Default knowledge base updated');
      loadKnowledgeBases();
    } catch {
      toast.error('Failed to set default');
    }
  };

  const saveEdit = async (id: number) => {
    try {
      await api.updateKnowledgeBase(id, { name: editName });
      toast.success('Knowledge base updated');
      setEditingId(null);
      loadKnowledgeBases();
    } catch {
      toast.error('Failed to update');
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
          <h1 className="text-2xl font-bold text-gray-100">Knowledge Bases</h1>
          <p className="text-gray-500">{knowledgeBases.length} knowledge bases</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Knowledge Base
        </button>
      </div>

      {showCreate && (
        <div className="bg-dark-100 rounded-xl border border-primary p-6">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">Create Knowledge Base</h3>
          <div className="space-y-4">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Name"
              className="input w-full"
            />
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Description (optional)"
              className="input w-full"
              rows={2}
            />
            <div className="flex gap-2">
              <button onClick={createKnowledgeBase} className="btn btn-primary">Create</button>
              <button onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {knowledgeBases.map(kb => (
          <div
            key={kb.id}
            className={`bg-dark-100 rounded-xl border p-6 ${kb.is_default ? 'border-primary' : 'border-dark-300'}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <Database className={`w-6 h-6 mt-1 ${kb.is_default ? 'text-primary' : 'text-gray-500'}`} />
                <div>
                  {editingId === kb.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="input"
                        autoFocus
                      />
                      <button onClick={() => saveEdit(kb.id)} className="text-green-400 hover:text-green-300">
                        <Check className="w-5 h-5" />
                      </button>
                      <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-300">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  ) : (
                    <h3 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
                      {kb.name}
                      {kb.is_default && <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />}
                    </h3>
                  )}
                  {kb.description && <p className="text-sm text-gray-500 mt-1">{kb.description}</p>}
                  <p className="text-sm text-gray-400 mt-2">{kb.document_count} documents</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!kb.is_default && (
                  <button
                    onClick={() => setDefault(kb.id)}
                    className="btn btn-secondary text-sm"
                    title="Set as default"
                  >
                    <Star className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => { setEditingId(kb.id); setEditName(kb.name); }}
                  className="btn btn-secondary text-sm"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteKnowledgeBase(kb.id)}
                  className="btn btn-secondary text-sm text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
