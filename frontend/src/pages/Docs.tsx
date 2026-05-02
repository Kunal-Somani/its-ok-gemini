import { Book, Code, Key, Terminal } from 'lucide-react';

export function Docs() {
  return (
    <div className="space-y-6">
      <div className="glass-card p-6 border-l-4 border-l-[#00ff9f]">
        <h1 className="text-2xl font-bold text-white mb-2">Documentation</h1>
        <p className="text-gray-400">Complete API reference and integration guide for the Agent Command Center.</p>
        <div className="mt-4">
          <a href="https://github.com/yourusername/agent-command-center" target="_blank" rel="noreferrer" className="text-[#00ff9f] hover:text-[#00cc7d] underline flex items-center gap-2">
            <Book size={16} /> View Full README on GitHub
          </a>
        </div>
      </div>

      <div className="glass-card p-6">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Key size={20} className="text-[#7c3aed]" />
          Authentication
        </h2>
        <p className="text-gray-400 mb-4">
          All API requests must include the <code className="bg-black/50 px-2 py-1 rounded text-[#00ff9f]">X-Api-Key</code> header to authenticate.
        </p>
        <pre className="bg-black/50 p-4 rounded-lg overflow-x-auto text-sm text-gray-300">
          <code>
            curl -H "X-Api-Key: your_api_key_here" http://localhost:8000/api/v1/tasks
          </code>
        </pre>
      </div>

      <div className="glass-card p-6">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Code size={20} className="text-[#7c3aed]" />
          API Quick Reference
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-gray-300">
            <thead className="text-xs text-gray-400 uppercase bg-black/30">
              <tr>
                <th className="px-6 py-3">Endpoint</th>
                <th className="px-6 py-3">Method</th>
                <th className="px-6 py-3">Description</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800">
                <td className="px-6 py-4 font-mono text-[#00ff9f]">/api/v1/tasks/ready</td>
                <td className="px-6 py-4"><span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded">POST</span></td>
                <td className="px-6 py-4">Create a new task queue item</td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="px-6 py-4 font-mono text-[#00ff9f]">/api/v1/tasks</td>
                <td className="px-6 py-4"><span className="bg-green-500/20 text-green-400 px-2 py-1 rounded">GET</span></td>
                <td className="px-6 py-4">List and filter tasks</td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="px-6 py-4 font-mono text-[#00ff9f]">/api/v1/tasks/{'{id}'}</td>
                <td className="px-6 py-4"><span className="bg-green-500/20 text-green-400 px-2 py-1 rounded">GET</span></td>
                <td className="px-6 py-4">Get specific task details</td>
              </tr>
              <tr>
                <td className="px-6 py-4 font-mono text-[#00ff9f]">/api/v1/tasks/{'{id}'}</td>
                <td className="px-6 py-4"><span className="bg-red-500/20 text-red-400 px-2 py-1 rounded">DELETE</span></td>
                <td className="px-6 py-4">Cancel a task</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="glass-card p-6">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Terminal size={20} className="text-[#7c3aed]" />
          WebSocket Usage
        </h2>
        <p className="text-gray-400 mb-4">
          Connect to the WebSocket to stream live structlogs directly from the execution terminal.
        </p>
        <pre className="bg-black/50 p-4 rounded-lg overflow-x-auto text-sm text-gray-300">
          <code>{`const ws = new WebSocket("ws://localhost:8000/ws/logs?task_id=abcd-1234");

ws.onmessage = (event) => {
    const log = JSON.parse(event.data);
    console.log(\`[\${log.level}] \${log.event}\`);
};`}</code>
        </pre>
      </div>
    </div>
  );
}
