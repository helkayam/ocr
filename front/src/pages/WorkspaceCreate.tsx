import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/Header';
import { Label } from '@/components/ui/label';
import { ArrowLeft, Folder, Sparkles, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { motion } from 'framer-motion';

export default function WorkspaceCreate() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error('Workspace name is required');
      return;
    }

    setIsSubmitting(true);

    try {
      const workspace = await api.workspaces.create({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      toast.success('Workspace created successfully');
      navigate(`/workspace/${workspace.id}`);
    } catch (err) {
      toast.error('Failed to create workspace');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />

      <main className="container mx-auto px-4 py-10 max-w-2xl">
        {/* Back button */}
        <motion.button
          whileHover={{ x: -3 }}
          whileTap={{ scale: 0.96 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Workspaces
        </motion.button>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
        >
          {/* Page header */}
          <div className="text-center mb-10">
            <motion.div
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.1, type: 'spring', stiffness: 320 }}
              className="inline-flex p-5 rounded-3xl mb-5"
              style={{
                background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                boxShadow: '0 8px 28px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.25)',
              }}
            >
              <Folder className="h-10 w-10 text-white" />
            </motion.div>
            <h1 className="text-4xl font-extrabold mb-2">
              <span className="text-foreground">Create </span>
              <span className="text-gradient">Workspace</span>
            </h1>
            <p className="text-muted-foreground text-base">
              Set up a new workspace to organize your files and documents
            </p>
          </div>

          {/* Form card */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div
              className="p-7 rounded-3xl bg-white border border-white/80 space-y-6"
              style={{ boxShadow: '0 8px 32px rgba(239,68,68,0.08), 0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.95)' }}
            >
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm font-bold">
                  Workspace Name{' '}
                  <span style={{ color: 'hsl(0,84%,58%)' }}>*</span>
                </Label>
                <input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Emergency Response Plans"
                  required
                  className="w-full px-4 py-2.5 rounded-2xl text-sm font-medium border outline-none transition-all duration-200"
                  style={{
                    background: 'hsl(0,0%,97%)',
                    borderColor: name ? 'hsl(0,84%,58%)' : 'hsl(0,0%,88%)',
                    boxShadow: name
                      ? '0 0 0 3px hsla(0,84%,60%,0.12), inset 0 1px 2px rgba(0,0,0,0.04)'
                      : 'inset 0 1px 2px rgba(0,0,0,0.04)',
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'hsl(0,84%,58%)';
                    e.target.style.boxShadow = '0 0 0 3px hsla(0,84%,60%,0.12), inset 0 1px 2px rgba(0,0,0,0.04)';
                  }}
                  onBlur={(e) => {
                    if (!name) {
                      e.target.style.borderColor = 'hsl(0,0%,88%)';
                      e.target.style.boxShadow = 'inset 0 1px 2px rgba(0,0,0,0.04)';
                    }
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  Choose a descriptive name for your workspace
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-sm font-bold">
                  Description{' '}
                  <span className="text-muted-foreground font-normal">(optional)</span>
                </Label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Briefly describe the purpose of this workspace..."
                  rows={4}
                  className="w-full px-4 py-2.5 rounded-2xl text-sm font-medium border outline-none transition-all duration-200 resize-none"
                  style={{
                    background: 'hsl(0,0%,97%)',
                    borderColor: 'hsl(0,0%,88%)',
                    boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.04)',
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'hsl(0,84%,58%)';
                    e.target.style.boxShadow = '0 0 0 3px hsla(0,84%,60%,0.12), inset 0 1px 2px rgba(0,0,0,0.04)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'hsl(0,0%,88%)';
                    e.target.style.boxShadow = 'inset 0 1px 2px rgba(0,0,0,0.04)';
                  }}
                />
              </div>
            </div>

            {/* Info card */}
            <div
              className="p-5 rounded-3xl border"
              style={{
                background: 'linear-gradient(135deg, hsla(0,84%,60%,0.04), hsla(0,84%,50%,0.04))',
                borderColor: 'hsla(0,84%,60%,0.18)',
                boxShadow: '0 2px 8px rgba(239,68,68,0.06)',
              }}
            >
              <div className="flex gap-3">
                <div
                  className="p-2 rounded-xl shrink-0 mt-0.5 self-start"
                  style={{
                    background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))',
                    boxShadow: '0 3px 8px rgba(239,68,68,0.3)',
                  }}
                >
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold text-foreground mb-2">What you can do with a workspace</p>
                  <ul className="text-sm text-muted-foreground space-y-1.5">
                    <li className="flex items-start gap-1.5">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: 'hsl(0,84%,55%)' }} />
                      Upload and organize PDF, DOCX, and GeoJSON documents
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: 'hsl(0,0%,40%)' }} />
                      Automatic file validation and structure verification
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: 'hsl(199,89%,55%)' }} />
                      Preview geographic data with interactive maps
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: 'hsl(158,64%,48%)' }} />
                      Track file status and manage your document library
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-3 pt-1">
              <motion.button
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => navigate('/')}
                className="flex-1 py-2.5 rounded-2xl text-sm font-bold text-muted-foreground border transition-all duration-200 hover:text-foreground"
                style={{
                  borderColor: 'hsl(0,0%,88%)',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.8)',
                }}
              >
                Cancel
              </motion.button>
              <motion.button
                type="submit"
                disabled={isSubmitting}
                whileHover={{ scale: isSubmitting ? 1 : 1.03 }}
                whileTap={{ scale: isSubmitting ? 1 : 0.97 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-2xl text-sm font-bold text-white disabled:opacity-70"
                style={{
                  background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                  boxShadow: '0 6px 20px rgba(239,68,68,0.42), inset 0 1px 0 rgba(255,255,255,0.25)',
                }}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating…
                  </>
                ) : (
                  'Create Workspace'
                )}
              </motion.button>
            </div>
          </form>
        </motion.div>
      </main>
    </div>
  );
}
