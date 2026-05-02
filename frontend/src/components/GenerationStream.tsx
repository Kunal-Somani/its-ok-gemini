import { useState, useEffect } from 'react';
import { WS_BASE } from '../config';

interface GenerationStreamProps {
  taskId: string;
  isGenerating: boolean;
}

export default function GenerationStream({ taskId, isGenerating }: GenerationStreamProps) {
  const [content, setContent] = useState('');
  const [tokenCount, setTokenCount] = useState(0);

  useEffect(() => {
    if (!isGenerating) return;
    const ws = new WebSocket(`${WS_BASE}/ws/generation/${taskId}`);
    
    ws.onmessage = (event) => {
      setContent((prev) => prev + event.data);
      setTokenCount((prev) => prev + 1);
    };

    return () => ws.close();
  }, [taskId, isGenerating]);

  if (!isGenerating) return null;

  return (
    <div className="glass-card rounded-xl border border-[#7c3aed]/30 p-6 shadow-[0_0_15px_rgba(124,58,237,0.1)]">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-mono tracking-widest text-[#7c3aed] uppercase flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#7c3aed] animate-pulse"></span>
          Live Generation Stream
        </h3>
        <span className="text-xs bg-[#7c3aed]/20 text-[#7c3aed] px-2 py-1 rounded border border-[#7c3aed]/30 font-mono">
          {tokenCount} tokens
        </span>
      </div>
      <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap overflow-x-auto max-h-96 overflow-y-auto p-4 bg-[#05050a]/80 rounded-lg border border-white/5 shadow-inner">
        {content || 'Connecting to LLM stream...'}
      </pre>
    </div>
  );
}
