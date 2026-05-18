import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { WorkspaceCard } from '@/components/WorkspaceCard';
import { SearchBar } from '@/components/SearchBar';
import { ConfirmDeleteModal } from '@/components/ConfirmDeleteModal';
import { api } from '@/lib/api';
import { Plus, FolderOpen } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';

export default function WorkspacesList() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingDelete, setPendingDelete] = useState<{ id: string; name: string } | null>(null);

  const { data: workspaces = [], isLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: api.workspaces.list,
  });

  const deleteMutation = useMutation({
    mutationFn: api.workspaces.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspaces'] });
      toast.success('Workspace deleted');
      setPendingDelete(null);
    },
    onError: () => {
      toast.error('Failed to delete workspace');
      setPendingDelete(null);
    },
  });

  const handleDelete = (id: string, name: string) => (e: React.MouseEvent) => {
    e.stopPropagation();
    setPendingDelete({ id, name });
  };

  const handleConfirmDelete = () => {
    if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
  };

  const filteredWorkspaces = workspaces.filter(workspace =>
    workspace.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    workspace.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen">
      <ConfirmDeleteModal
        isOpen={pendingDelete !== null}
        workspaceName={pendingDelete?.name ?? ''}
        isDeleting={deleteMutation.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={handleConfirmDelete}
      />
      <Header />

      <main className="container mx-auto px-4 py-10">
        {/* Hero Section */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="text-center mb-14"
        >
          {/* Decorative badge */}
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 300 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-5 text-sm font-semibold text-white"
            style={{
              background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
              boxShadow: '0 4px 16px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.25)',
            }}
          >
            <span className="h-2 w-2 rounded-full bg-white/80 animate-pulse" />
            Document Intelligence Platform
          </motion.div>

          <h1 className="text-5xl md:text-6xl font-extrabold mb-4 leading-tight">
            <span className="text-foreground">Digital </span>
            <span className="text-gradient">Librarian</span>
          </h1>

        </motion.div>

        {/* Actions Bar */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.4 }}
          className="flex flex-col sm:flex-row gap-4 mb-10 items-start sm:items-center justify-between"
        >
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search workspaces..."
            className="w-full sm:w-80"
          />

          <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }} transition={{ type: 'spring', stiffness: 400, damping: 18 }}>
            <button
              onClick={() => navigate('/create')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold text-white whitespace-nowrap"
              style={{
                background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                boxShadow: '0 6px 20px rgba(239,68,68,0.42), inset 0 1px 0 rgba(255,255,255,0.25)',
              }}
            >
              <Plus className="h-4 w-4" />
              Create New Workspace
            </button>
          </motion.div>
        </motion.div>

        {/* Workspaces Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div
                key={i}
                className="h-52 rounded-3xl animate-pulse"
                style={{ background: 'linear-gradient(135deg, hsl(0,0%,96%), hsl(0,0%,93%))' }}
              />
            ))}
          </div>
        ) : filteredWorkspaces.length > 0 ? (
          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-stretch"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: 0.08 } },
            }}
          >
            {filteredWorkspaces.map((workspace) => (
              <motion.div
                key={workspace.id}
                className="h-full"
                variants={{
                  hidden: { opacity: 0, y: 24, scale: 0.97 },
                  visible: { opacity: 1, y: 0, scale: 1, transition: { type: 'spring', stiffness: 300, damping: 24 } },
                }}
              >
                <WorkspaceCard
                  workspace={workspace}
                  onClick={() => navigate(`/workspace/${workspace.id}`)}
                  onDelete={handleDelete(workspace.id, workspace.name)}
                />
              </motion.div>
            ))}
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 280 }}
            className="text-center py-24"
          >
            <div
              className="inline-flex p-6 rounded-3xl mb-6"
              style={{
                background: 'linear-gradient(135deg, hsl(0,0%,96%), hsl(0,0%,93%))',
                boxShadow: '0 4px 16px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
              }}
            >
              <FolderOpen className="h-14 w-14 text-muted-foreground/40" />
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-2">No workspaces found</h3>
            <p className="text-muted-foreground mb-8 text-base">
              {searchQuery ? 'Try a different search term' : 'Create your first workspace to get started'}
            </p>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 400, damping: 18 }}
              onClick={() => navigate('/create')}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl text-sm font-bold text-white"
              style={{
                background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                boxShadow: '0 6px 20px rgba(239,68,68,0.42), inset 0 1px 0 rgba(255,255,255,0.25)',
              }}
            >
              <Plus className="h-4 w-4" />
              Create Workspace
            </motion.button>
          </motion.div>
        )}
      </main>
    </div>
  );
}
