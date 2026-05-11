import { Search, X } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

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
      <div
        className="relative flex items-center rounded-2xl bg-white border transition-all duration-200"
        style={{
          borderColor: isFocused ? 'hsl(0,84%,58%)' : 'hsl(0,0%,88%)',
          boxShadow: isFocused
            ? '0 0 0 3px hsla(0,84%,60%,0.12), 0 4px 12px rgba(239,68,68,0.10), inset 0 1px 0 rgba(255,255,255,0.9)'
            : '0 2px 8px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.8)',
        }}
      >
        <Search
          className="absolute left-3.5 h-4 w-4 pointer-events-none transition-colors duration-200"
          style={{ color: isFocused ? 'hsl(0,84%,55%)' : 'hsl(0,0%,52%)' }}
        />

        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          className="w-full bg-transparent py-2.5 pl-10 pr-10 text-sm focus:outline-none placeholder:text-muted-foreground font-medium"
        />

        <AnimatePresence>
          {value && (
            <motion.button
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              onClick={() => onChange('')}
              className="absolute right-3 p-1 rounded-xl hover:bg-muted transition-colors"
            >
              <X className="h-3.5 w-3.5 text-muted-foreground" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
