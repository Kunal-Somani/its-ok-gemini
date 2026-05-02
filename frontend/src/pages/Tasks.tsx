import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTasks } from '../api/client';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import StatusBadge from '../components/StatusBadge';
import { Search } from 'lucide-react';

const STATUSES = ['All', 'QUEUED', 'ANALYZING', 'GENERATING', 'DEPLOYING', 'SUCCESS', 'FAILED'];

export default function Tasks() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
    refetchInterval: 5000,
  });

  const filteredTasks = tasks.filter(t => {
    if (filter !== 'All' && t.status !== filter) return false;
    if (search && !t.task_name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
          <input 
            type="text" 
            placeholder="Search tasks..." 
            className="w-full sm:w-80 bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-[#00ff9f] transition-colors"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {STATUSES.map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium tracking-wide transition-colors ${filter === s ? 'bg-[#7c3aed] text-white shadow-[0_0_10px_rgba(124,58,237,0.4)]' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="glass-card rounded-xl overflow-hidden border border-white/5">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 text-xs font-mono tracking-wider text-slate-400 uppercase bg-black/20">
              <th className="p-4">Task Name</th>
              <th className="p-4">Status</th>
              <th className="p-4">Duration</th>
              <th className="p-4">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filteredTasks.map((task) => (
              <tr 
                key={task.id} 
                onClick={() => navigate(`/tasks/${task.id}`)}
                className="hover:bg-white/5 cursor-pointer transition-colors group"
              >
                <td className="p-4 font-medium text-slate-200 group-hover:text-[#00ff9f] transition-colors">{task.task_name}</td>
                <td className="p-4"><StatusBadge status={task.status} /></td>
                <td className="p-4 text-slate-400 font-mono text-sm">{task.duration_seconds ? `${Math.round(task.duration_seconds)}s` : '-'}</td>
                <td className="p-4 text-sm text-slate-500">
                  {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
                </td>
              </tr>
            ))}
            {filteredTasks.length === 0 && !isLoading && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-slate-500 italic">No tasks found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
