import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/Header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ArrowLeft, Folder, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';

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
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <Button
          variant="ghost"
          size="sm"
          className="mb-6"
          onClick={() => navigate('/')}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workspaces
        </Button>

        <div className="animate-fade-in">
          <div className="text-center mb-8">
            <div className="inline-flex p-4 rounded-2xl bg-primary/10 mb-4">
              <Folder className="h-10 w-10 text-primary" />
            </div>
            <h1 className="text-3xl font-bold text-foreground mb-2">
              Create New Workspace
            </h1>
            <p className="text-muted-foreground">
              Set up a new workspace to organize your files and documents
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="p-6 rounded-xl bg-card border border-border space-y-6">
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm font-medium">
                  Workspace Name <span className="text-primary">*</span>
                </Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Emergency Response Plans"
                  className="bg-muted/50 border-border focus:border-primary"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Choose a descriptive name for your workspace
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-sm font-medium">
                  Description <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Briefly describe the purpose of this workspace..."
                  className="bg-muted/50 border-border focus:border-primary min-h-[100px] resize-none"
                  rows={4}
                />
              </div>
            </div>

            {/* Info Card */}
            <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
              <div className="flex gap-3">
                <Sparkles className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-foreground mb-1">
                    What you can do with a workspace
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• Upload and organize PDF, DOCX, GeoJSON, and Shapefile documents</li>
                    <li>• Automatic file validation and structure verification</li>
                    <li>• Preview geographic data with mini-maps</li>
                    <li>• Track file status and manage your document library</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => navigate('/')}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="hero"
                size="lg"
                className="flex-1"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="animate-spin mr-2">⏳</span>
                    Creating...
                  </>
                ) : (
                  'Create Workspace'
                )}
              </Button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
