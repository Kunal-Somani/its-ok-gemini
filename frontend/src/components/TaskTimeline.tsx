import clsx from 'clsx';
import { Check } from 'lucide-react';
import { TaskRecord } from '../api/client';
import { format } from 'date-fns';

interface TaskTimelineProps {
  task: TaskRecord;
}

export default function TaskTimeline({ task }: TaskTimelineProps) {
  const currentStatus = task.status;
  const steps = ['QUEUED', 'ANALYZING', 'GENERATING', 'DEPLOYING', 'SUCCESS'];
  
  const isFailed = currentStatus === 'FAILED';
  const effectiveSteps = isFailed ? ['QUEUED', 'ANALYZING', 'GENERATING', 'DEPLOYING', 'FAILED'] : steps;
  
  let currentIndex = effectiveSteps.indexOf(currentStatus);
  if (currentIndex === -1) currentIndex = 0;
  if (currentStatus === 'SUCCESS' || currentStatus === 'FAILED') currentIndex = 4;

  return (
    <div className="glass-card p-6 rounded-xl mb-6">
      <div className="flex items-center justify-between relative max-w-3xl mx-auto">
        <div className="absolute left-10 right-10 top-1/2 h-[2px] bg-white/5 -translate-y-1/2 z-0"></div>
        <div 
          className="absolute left-10 top-1/2 h-[2px] bg-gradient-to-r from-[#7c3aed] to-[#00ff9f] -translate-y-1/2 z-0 transition-all duration-500"
          style={{ width: `${(currentIndex / 4) * 100}%`, maxWidth: 'calc(100% - 5rem)' }}
        ></div>
        
        {effectiveSteps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;
          const isEndState = index === 4;
          
          let circleBg = 'bg-[#1a1a24] border-white/10 text-slate-500';
          if (isCompleted) circleBg = 'bg-[#7c3aed] border-[#7c3aed] text-white shadow-[0_0_10px_rgba(124,58,237,0.5)]';
          if (isCurrent && !isEndState) circleBg = 'bg-[#0a0a0f] border-[#00ff9f] text-[#00ff9f] shadow-[0_0_15px_rgba(0,255,159,0.3)] animate-pulse';
          if (isCurrent && isEndState && currentStatus === 'SUCCESS') circleBg = 'bg-[#00ff9f] border-[#00ff9f] text-[#0a0a0f] shadow-[0_0_15px_rgba(0,255,159,0.5)]';
          if (isCurrent && isEndState && currentStatus === 'FAILED') circleBg = 'bg-red-500 border-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]';

          return (
            <div key={step} className="flex flex-col items-center gap-3 z-10 w-24 relative group">
              <div className={clsx("w-8 h-8 rounded-full border-2 flex items-center justify-center transition-colors duration-300", circleBg)}>
                {isCompleted || (isEndState && currentStatus === 'SUCCESS') ? <Check size={16} strokeWidth={3} /> : <span className="text-xs font-bold">{index + 1}</span>}
              </div>
              <div className="flex flex-col items-center">
                <span className={clsx(
                  "text-[11px] font-mono tracking-wider uppercase text-center",
                  isCurrent ? (isFailed ? 'text-red-400 font-bold' : 'text-[#00ff9f] font-bold') : (isCompleted ? 'text-slate-300' : 'text-slate-600')
                )}>
                  {step}
                </span>
                {task.step_timestamps && task.step_timestamps[step] && (
                  <span className="text-[10px] text-slate-500 mt-1 font-mono">{format(new Date(task.step_timestamps[step]), 'HH:mm:ss')}</span>
                )}
              </div>
              
              {/* Optional duration text above line */}
              {isCompleted && task.step_durations && task.step_durations[step] && (
                <div className="absolute -right-12 top-0 -translate-y-6 text-[10px] text-slate-400 font-mono">
                  {task.step_durations[step]}
                </div>
              )}

              {/* Error log inline */}
              {isEndState && isFailed && task.error_log && step === 'FAILED' && (
                <div className="absolute top-16 w-48 text-center text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 p-2 rounded max-h-24 overflow-hidden text-ellipsis">
                  {task.error_log}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
