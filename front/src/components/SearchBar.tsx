import { Search, X } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchBar({ value, onChange, placeholder = 'Search files...', className }: SearchBarProps) {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div className={cn('relative', className)}>
      <div className={cn(
        'relative flex items-center transition-all duration-300',
        'bg-card border rounded-lg overflow-hidden',
        isFocused ? 'border-primary ring-2 ring-primary/20' : 'border-border'
      )}>
        <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
        
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          className={cn(
            'w-full bg-transparent py-2.5 pl-10 pr-10 text-sm',
            'placeholder:text-muted-foreground',
            'focus:outline-none'
          )}
        />

        {value && (
          <button
            onClick={() => onChange('')}
            className="absolute right-3 p-1 rounded-full hover:bg-muted transition-colors"
          >
            <X className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        )}
      </div>
      
      {/* Underline effect */}
      <div className={cn(
        'absolute bottom-0 left-1/2 -translate-x-1/2 h-0.5 bg-primary transition-all duration-300',
        isFocused ? 'w-full' : 'w-0'
      )} />
    </div>
  );
}
