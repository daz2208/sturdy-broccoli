'use client';
import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { FolderOpen, Download } from 'lucide-react';
import type { Cluster } from '@/types/api';

export default function ClustersPage() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadClusters(); }, []);

  const loadClusters = async () => {
    try { const data = await api.getClusters(); setClusters(data.clusters); }
    catch { toast.error('Failed to load clusters'); }
    finally { setLoading(false); }
  };

  const exportCluster = async (id: number, format: 'json' | 'markdown') => {
    try {
      const blob = await api.exportCluster(id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cluster-${id}.${format === 'json' ? 'json' : 'md'}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Export downloaded');
    } catch { toast.error('Export failed'); }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;

  return (
    <div className="space-y-6 animate-fadeIn">
      <div><h1 className="text-2xl font-bold text-gray-100">Clusters</h1><p className="text-gray-500">{clusters.length} topic clusters</p></div>
      <div className="grid gap-4">
        {clusters.map(cluster => (
          <div key={cluster.id} className="bg-dark-100 rounded-xl border border-dark-300 p-6 border-l-4 border-l-primary">
            <div className="flex justify-between items-start">
              <div className="flex items-start gap-4">
                <FolderOpen className="w-6 h-6 text-primary mt-1" />
                <div>
                  <h3 className="text-lg font-semibold text-gray-200">{cluster.name}</h3>
                  <p className="text-sm text-gray-500">{cluster.doc_ids.length} documents</p>
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {cluster.concepts.slice(0, 5).map((c, i) => <span key={i} className="badge badge-primary">{c}</span>)}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => exportCluster(cluster.id, 'json')} className="btn btn-secondary text-sm"><Download className="w-4 h-4" /></button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
