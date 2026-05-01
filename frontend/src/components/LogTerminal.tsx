import React, { useState, useEffect, useRef } from 'react';
import { WS_BASE } from '../config';
import { TerminalSquare, Copy, ArrowDown } from 'lucide-react';

interface LogTerminalProps {
  taskId: string;
}

export default function LogTerminal({ taskId }: LogTerminalProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/logs?task_id=${taskId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      setLogs((prev) => [...prev, event.data]);
    };

    return () => {
      ws.close();
    };
  }, [taskId]);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const copyLogs = () => {
    navigator.clipboard.writeText(logs.join('\n'));
  };

  const formatLog = (log: string, index: number) => {
    try {
      const parsed = JSON.parse(log);
      const level = parsed.level || 'INFO';
      const event = parsed.event || '';
      
      let color = 'text-slate-300';
      if (level === 'error' || level === 'ERROR') color = 'text-red-400';
      if (level === 'warning' || level === 'WARNING') color = 'text-yellow-400';
      if (level === 'info' || level === 'INFO') color = 'text-cyan-400';

      return (
        <div key={index} className="mb-1 font-mono text-[13px] leading-relaxed break-all">
          <span className="text-slate-500 mr-2">[{parsed.timestamp || new Date().toISOString()}]</span>
          <span className={`font-semibold mr-2 ${color}`}>[{level.toUpperCase()}]</span>
          <span className="text-slate-300">{event}</span>
          {Object.entries(parsed).map(([k, v]) => {
            if (['level', 'event', 'timestamp', 'logger', 'task_id'].includes(k)) return null;
            return <span key={k} className="ml-2 text-slate-500">{k}=<span className="text-slate-400">{JSON.stringify(v)}</span></span>;
          })}
        </div>
      );
    } catch {
      return <div key={index} className="mb-1 font-mono text-[13px] leading-relaxed text-slate-300 break-all">{log}</div>;
    }
  };

  return (
    <div className="flex flex-col h-full rounded-xl overflow-hidden glass-card terminal-glow">
      <div className="bg-black/40 px-4 py-3 flex items-center justify-between border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2 text-slate-400">
          <TerminalSquare size={16} />
          <span className="text-sm font-medium font-mono uppercase tracking-wider">Live Logs</span>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded-md transition-colors ${autoScroll ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-white'}`}
            title="Auto-scroll"
          >
            <ArrowDown size={14} />
          </button>
          <button 
            onClick={copyLogs}
            className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-colors"
            title="Copy all"
          >
            <Copy size={14} />
          </button>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 bg-[#05050a]/80 scrollbar-hide">
        {logs.length === 0 ? (
          <div className="text-slate-500 text-sm font-mono italic">Waiting for logs...</div>
        ) : (
          logs.map((log, i) => formatLog(log, i))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
