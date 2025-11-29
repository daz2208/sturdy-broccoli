'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Tag as TagIcon, Plus, X, Trash2, FileText, Loader2, RefreshCw } from 'lucide-react';
import type { Tag } from '@/types/api';

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState('#3b82f6');
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => {
    loadTags();
  }, []);

  const loadTags = async () => {
    try {
      const data = await api.getTags();
      setTags(data.tags);
    } catch (err) {
      toast.error('Failed to load tags');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const createTag = async () => {
    if (!newTagName.trim()) {
      toast.error('Tag name is required');
      return;
    }

    setCreating(true);
    try {
      const tag = await api.createTag(newTagName.trim(), newTagColor);
      setTags(prev => [...prev, tag]);
      setNewTagName('');
      setNewTagColor('#3b82f6');
      setShowCreate(false);
      toast.success('Tag created');
    } catch (err) {
      toast.error('Failed to create tag');
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const deleteTag = async (tagId: number) => {
    if (!confirm('Delete this tag? It will be removed from all documents.')) return;

    setDeleting(tagId);
    try {
      await api.deleteTag(tagId);
      setTags(prev => prev.filter(t => t.id !== tagId));
      toast.success('Tag deleted');
    } catch (err) {
      toast.error('Failed to delete tag');
      console.error(err);
    } finally {
      setDeleting(null);
    }
  };

  const predefinedColors = [
    '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
    '#22c55e', '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9',
    '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef',
    '#ec4899', '#f43f5e'
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <TagIcon className="w-6 h-6 text-accent-blue" />
            Tags
          </h1>
          <p className="text-gray-500 mt-1">
            Organize your documents with custom tags
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={loadTags}
            className="btn btn-secondary flex items-center gap-2"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Tag
          </button>
        </div>
      </div>

      {/* Create Tag Form */}
      {showCreate && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">Create New Tag</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Tag Name *</label>
              <input
                type="text"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                placeholder="e.g., Important, Machine Learning, To Review"
                className="input w-full"
                maxLength={50}
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">Color</label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={newTagColor}
                  onChange={(e) => setNewTagColor(e.target.value)}
                  className="h-10 w-20 rounded cursor-pointer"
                />
                <div className="flex flex-wrap gap-2">
                  {predefinedColors.map(color => (
                    <button
                      key={color}
                      onClick={() => setNewTagColor(color)}
                      className={`w-6 h-6 rounded-full transition-transform hover:scale-110 ${
                        newTagColor === color ? 'ring-2 ring-white ring-offset-2 ring-offset-dark-100' : ''
                      }`}
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                  ))}
                </div>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-sm text-gray-500">Preview:</span>
                <span
                  className="px-3 py-1 rounded-full text-sm font-medium text-white"
                  style={{ backgroundColor: newTagColor }}
                >
                  {newTagName || 'Tag Name'}
                </span>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={createTag}
                disabled={creating || !newTagName.trim()}
                className="btn btn-primary"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Tag
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowCreate(false);
                  setNewTagName('');
                  setNewTagColor('#3b82f6');
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tags List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
        </div>
      ) : tags.length === 0 ? (
        <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
          <TagIcon className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300">No tags yet</h3>
          <p className="text-gray-500 mt-2 max-w-md mx-auto">
            Create tags to organize your documents by topic, priority, or any custom categories.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="btn btn-primary mt-4"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Your First Tag
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {tags.map(tag => (
            <TagCard
              key={tag.id}
              tag={tag}
              onDelete={deleteTag}
              deleting={deleting === tag.id}
            />
          ))}
        </div>
      )}

      {/* Stats */}
      {tags.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h3 className="text-lg font-semibold text-gray-200 mb-4">Tag Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Total Tags</p>
              <p className="text-2xl font-bold text-white">{tags.length}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Total Usage</p>
              <p className="text-2xl font-bold text-white">
                {tags.reduce((sum, tag) => sum + (tag.usage_count || 0), 0)}
              </p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Most Used</p>
              <p className="text-sm font-medium text-white truncate">
                {tags.sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))[0]?.name || 'N/A'}
              </p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Avg per Tag</p>
              <p className="text-2xl font-bold text-white">
                {tags.length > 0 ? Math.round(tags.reduce((sum, tag) => sum + (tag.usage_count || 0), 0) / tags.length) : 0}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TagCard({
  tag,
  onDelete,
  deleting
}: {
  tag: Tag;
  onDelete: (tagId: number) => void;
  deleting: boolean;
}) {
  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 p-5 hover:border-dark-200 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className="px-3 py-1 rounded-full text-sm font-medium text-white"
            style={{ backgroundColor: tag.color || '#3b82f6' }}
          >
            {tag.name}
          </span>
        </div>
        <button
          onClick={() => onDelete(tag.id)}
          disabled={deleting}
          className="p-1 text-gray-400 hover:text-red-400 transition-colors"
          title="Delete tag"
        >
          {deleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <FileText className="w-4 h-4" />
          <span>
            {tag.usage_count || 0} {tag.usage_count === 1 ? 'document' : 'documents'}
          </span>
        </div>
      </div>
    </div>
  );
}
