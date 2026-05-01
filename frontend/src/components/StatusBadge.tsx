import React from 'react';
import clsx from 'clsx';

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  let colorClass = '';
  let dotAnimation = '';
  let dotColor = '';

  switch (status) {
    case 'QUEUED':
      colorClass = 'bg-gray-500/10 text-gray-400 border-gray-500/20';
      dotColor = 'bg-gray-400';
      break;
    case 'ANALYZING':
      colorClass = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      dotAnimation = 'animate-pulse-dot-blue shadow-[0_0_8px_#3b82f6]';
      dotColor = 'bg-blue-400';
      break;
    case 'GENERATING':
      colorClass = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      dotAnimation = 'animate-pulse-dot-purple shadow-[0_0_8px_#7c3aed]';
      dotColor = 'bg-purple-400';
      break;
    case 'DEPLOYING':
      colorClass = 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      dotAnimation = 'animate-pulse-dot-orange shadow-[0_0_8px_#f97316]';
      dotColor = 'bg-orange-400';
      break;
    case 'SUCCESS':
      colorClass = 'bg-[#00ff9f]/10 text-[#00ff9f] border-[#00ff9f]/20';
      dotColor = 'bg-[#00ff9f] shadow-[0_0_8px_#00ff9f]';
      break;
    case 'FAILED':
      colorClass = 'bg-red-500/10 text-red-400 border-red-500/20';
      dotColor = 'bg-red-500 shadow-[0_0_8px_#ef4444]';
      break;
    default:
      colorClass = 'bg-gray-500/10 text-gray-400 border-gray-500/20';
      dotColor = 'bg-gray-400';
  }

  return (
    <div className={clsx(
      "inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono tracking-wide border",
      colorClass
    )}>
      <div className={clsx("w-1.5 h-1.5 rounded-full", dotColor, dotAnimation)} />
      {status}
    </div>
  );
}
