import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTask, cancelTask } from '../api/client';
import { ArrowLeft, ExternalLink, XCircle, Github, Globe } from 'lucide-react';
import { format } from 'date-fns';
import TaskTimeline from '../components/TaskTimeline';
import LogTerminal from '../components/LogTerminal';
import StatusBadge from '../components/StatusBadge';
import GenerationStream from '../components/GenerationStream';

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: task, isLoading } = useQuery({
    queryKey: ['task', id],
    queryFn: () => getTask(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && !['SUCCESS', 'FAILED'].includes(data.status) ? 3000 : false;
    }
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelTask(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', id] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      navigate('/tasks');
    }
  });

  if (isLoading || !task) {
    return <div className="text-center py-10 text-slate-500 font-mono">LOADING TASK DATA...</div>;
  }

  const isActive = !['SUCCESS', 'FAILED'].includes(task.status);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-6">
      <div className="flex items-center gap-4 shrink-0">
        <button onClick={() => navigate('/tasks')} className="p-2 bg-white/5 hover:bg-white/10 rounded-full transition-colors text-slate-400 hover:text-white">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1 flex items-center gap-4">
          <h2 className="text-2xl font-bold text-white">{task.task_name}</h2>
          <StatusBadge status={task.status} />
          {task.retry_count && task.retry_count > 0 ? (
            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
              Retried {task.retry_count}x
            </span>
          ) : null}
        </div>
        {isActive && (
          <button 
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors font-medium text-sm tracking-wide disabled:opacity-50 shadow-[0_0_15px_rgba(239,68,68,0.2)]"
          >
            <XCircle size={16} />
            ABORT
          </button>
        )}
      </div>

      <TaskTimeline task={task} />

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Metadata */}
        <div className="lg:col-span-1 space-y-6 overflow-y-auto scrollbar-hide pr-2">
          <div className="glass-card rounded-xl border border-white/5 p-6 space-y-6">
            <div>
              <h3 className="text-xs font-mono tracking-widest text-slate-500 uppercase mb-4">Metadata</h3>
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Task ID</p>
                  <p className="font-mono text-sm text-slate-300 break-all">{task.id}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Created At</p>
                  <p className="font-mono text-sm text-slate-300">{format(new Date(task.created_at), 'PPpp')}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Email / Owner</p>
                  <p className="text-sm text-slate-300">{task.email}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Duration</p>
                  <p className="font-mono text-sm text-slate-300">{task.duration_seconds ? `${task.duration_seconds}s` : 'Running...'}</p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-white/5">
              <h3 className="text-xs font-mono tracking-widest text-slate-500 uppercase mb-4">Outputs</h3>
              <div className="space-y-3">
                {task.repo_url && (
                  <a href={task.repo_url} target="_blank" rel="noreferrer" className="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 group">
                    <Github size={18} className="text-slate-400 group-hover:text-white" /> 
                    <span className="text-sm font-medium text-slate-300 group-hover:text-white flex-1">Repository</span>
                    <ExternalLink size={14} className="text-slate-500" />
                  </a>
                )}
                {task.pages_url && (
                  <a href={task.pages_url} target="_blank" rel="noreferrer" className="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/5 group">
                    <Globe size={18} className="text-[#00ff9f]" /> 
                    <span className="text-sm font-medium text-slate-300 group-hover:text-[#00ff9f] flex-1">Live Preview</span>
                    <ExternalLink size={14} className="text-[#00ff9f]/50" />
                  </a>
                )}
                {!task.repo_url && !task.pages_url && (
                  <p className="text-slate-500 text-sm italic font-mono">Awaiting deployment...</p>
                )}
              </div>
            </div>
            
            {task.error_log && (
              <div className="pt-4 border-t border-white/5">
                <h3 className="text-xs font-mono tracking-widest text-red-500 uppercase mb-4">Error Log</h3>
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <pre className="text-xs text-red-400 whitespace-pre-wrap font-mono">{task.error_log}</pre>
                </div>
              </div>
            )}
            <GenerationStream taskId={task.id} isGenerating={task.status === 'GENERATING'} />
          </div>
        </div>

        {/* Right: Terminal */}
        <div className="lg:col-span-2 h-[500px] lg:h-full">
          <LogTerminal taskId={task.id} />
        </div>
      </div>
    </div>
  );
}
