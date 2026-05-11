import React from 'react';
import { CitedSource } from '@/types/files';
import { CitationLink } from './CitationLink';

interface AnswerBodyProps {
  body: string;
  sources: CitedSource[];
  onCitationClick: (source: CitedSource) => void;
}

// ---------------------------------------------------------------------------
// Regex construction
// ---------------------------------------------------------------------------
// The Hebrew word for "page" is assembled letter-by-letter using \uXXXX
// escapes so the regex is immune to RTL visual reordering that some editors
// apply when Hebrew characters are typed or pasted directly into source files.
//
//   ע = ע (ayin)   מ = מ (mem)
//   ו = ו (vav)    ד = ד (dalet)
//
// Together they spell עמוד (amud = "page").
//
// Pattern captures group 1: the digit+comma payload, e.g. "4" or "1, 18".
const _AMUD = 'ע' + 'מ' + 'ו' + 'ד';
const _CITE_PATTERN = '\\(' + _AMUD + '\\s+(\\d+(?:\\s*,\\s*\\d+)*)\\)';

/** Returns a fresh /g RegExp — avoids shared lastIndex across calls. */
function makeCitationRe(): RegExp {
  return new RegExp(_CITE_PATTERN, 'g');
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------
function parseWithCitations(
  text: string,
  sources: CitedSource[],
  onCitationClick: (source: CitedSource) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const re = makeCitationRe();
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    // Plain text before this citation group
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    // Extract every page number: "1, 18" → [1, 18]
    const pageNumbers = (match[1].match(/\d+/g) ?? []).map(Number);

    // Rebuild as interactive chips, keeping the surrounding parentheses
    nodes.push('(');
    pageNumbers.forEach((pageNum, idx) => {
      if (idx > 0) nodes.push(', ');
      const source = sources.find(s => s.page_num === pageNum) ?? null;
      nodes.push(
        <CitationLink
          key={`${match!.index}-${pageNum}`}
          pageNum={pageNum}
          source={source}
          onClick={source ? () => onCitationClick(source) : undefined}
        />,
      );
    });
    nodes.push(')');

    lastIndex = match.index + match[0].length;
  }

  // Trailing plain text after the last citation
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function AnswerBody({ body, sources, onCitationClick }: AnswerBodyProps) {
  const nodes = parseWithCitations(body, sources, onCitationClick);

  return (
    <div
      dir="rtl"
      lang="he"
      className="text-sm text-foreground leading-relaxed whitespace-pre-wrap"
    >
      {nodes}
    </div>
  );
}
