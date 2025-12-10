import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/Header';
import { WorkspaceCard } from '@/components/WorkspaceCard';
import { SearchBar } from '@/components/SearchBar';
import { Button } from '@/components/ui/button';
import { Workspace } from '@/types/files';
import { Plus, FolderOpen } from 'lucide-react';

// Mock data
const mockWorkspaces: Workspace[] = [
  {
    id: '1',
    name: 'Emergency Response Plans',
    description: 'Critical documentation for disaster response protocols and evacuation procedures.',
    createdAt: new Date('2024-01-15'),
    updatedAt: new Date('2024-03-10'),
    fileCount: 24,
    totalSize: 156000000,
  },
  {
    id: '2',
    name: 'GIS Mapping Data',
    description: 'Geographic information system files for regional coverage analysis.',
    createdAt: new Date('2024-02-20'),
    updatedAt: new Date('2024-03-08'),
    fileCount: 12,
    totalSize: 89000000,
  },
  {
    id: '3',
    name: 'Operational Guidelines',
    description: 'Standard operating procedures and training materials for field operations.',
    createdAt: new Date('2024-03-01'),
    updatedAt: new Date('2024-03-12'),
    fileCount: 45,
    totalSize: 234000000,
  },
  {
    id: '4',
    name: 'Infrastructure Assessment',
    description: 'Structural analysis reports and site survey documentation.',
    createdAt: new Date('2024-02-10'),
    updatedAt: new Date('2024-03-05'),
    fileCount: 18,
    totalSize: 178000000,
  },
];

export default function WorkspacesList() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredWorkspaces = mockWorkspaces.filter(workspace =>
    workspace.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    workspace.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-8">
        {/* Hero Section */}
        <div className="text-center mb-12 animate-fade-in">
          <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
            Digital Librarian
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Secure document management system for emergency organizations. 
            Upload, organize, and validate critical files with confidence.
          </p>
        </div>

        {/* Actions Bar */}
        <div className="flex flex-col sm:flex-row gap-4 mb-8 items-start sm:items-center justify-between animate-fade-in" style={{ animationDelay: '100ms' }}>
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search workspaces..."
            className="w-full sm:w-80"
          />
          
          <Button variant="hero" size="lg" onClick={() => navigate('/create')}>
            <Plus className="h-5 w-5 mr-2" />
            Create New Workspace
          </Button>
        </div>

        {/* Workspaces Grid */}
        {filteredWorkspaces.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fade-in" style={{ animationDelay: '200ms' }}>
            {filteredWorkspaces.map((workspace, index) => (
              <div
                key={workspace.id}
                className="animate-fade-in"
                style={{ animationDelay: `${(index + 3) * 100}ms` }}
              >
                <WorkspaceCard
                  workspace={workspace}
                  onClick={() => navigate(`/workspace/${workspace.id}`)}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 animate-fade-in">
            <FolderOpen className="h-16 w-16 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-xl font-medium text-foreground mb-2">No workspaces found</h3>
            <p className="text-muted-foreground mb-6">
              {searchQuery ? 'Try a different search term' : 'Create your first workspace to get started'}
            </p>
            <Button variant="default" onClick={() => navigate('/create')}>
              <Plus className="h-4 w-4 mr-2" />
              Create Workspace
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
