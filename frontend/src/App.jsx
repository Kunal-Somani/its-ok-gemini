import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import './App.css'

// ============================================================================
// Task Table Component
// ============================================================================

const TaskTable = () => {
  const { data: tasks = [], isLoading, error } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/api/v1/tasks')
      if (!response.ok) throw new Error('Failed to fetch tasks')
      return response.json()
    },
    refetchInterval: 5000, // Refetch every 5 seconds
  })

  const getStatusColor = (status) => {
    const colors = {
      QUEUED: 'bg-gray-500',
      ANALYZING: 'bg-blue-500',
      GENERATING: 'bg-purple-500',
      DEPLOYING: 'bg-yellow-500',
      SUCCESS: 'bg-green-500',
      FAILED: 'bg-red-500',
    }
    return colors[status] || 'bg-gray-400'
  }

  if (isLoading) return <div className="p-4 text-sm text-gray-400">Loading tasks...</div>
  if (error) return <div className="p-4 text-sm text-red-400">Error: {error.message}</div>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="px-4 py-3 text-left text-gray-300">Task Name</th>
            <th className="px-4 py-3 text-left text-gray-300">Status</th>
            <th className="px-4 py-3 text-left text-gray-300">Live Preview</th>
            <th className="px-4 py-3 text-left text-gray-300">Created</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id} className="border-b border-gray-800 hover:bg-gray-900">
              <td className="px-4 py-3 text-gray-100 font-medium">{task.task_name}</td>
              <td className="px-4 py-3">
                <span className={`px-2 py-1 rounded text-white text-xs font-semibold ${getStatusColor(task.status)}`}>
                  {task.status}
                </span>
              </td>
              <td className="px-4 py-3">
                {task.pages_url ? (
                  <a
                    href={task.pages_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline"
                  >
                    Live
                  </a>
                ) : (
                  <span className="text-gray-500">-</span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-400">
                {new Date(task.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {tasks.length === 0 && <div className="p-4 text-center text-gray-400">No tasks yet</div>}
    </div>
  )
}

// ============================================================================
// Metrics Bar Component
// ============================================================================

const MetricsBar = () => {
  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks-metrics'],
    queryFn: async () => {
      const response = await fetch('http://localhost:8000/api/v1/tasks')
      if (!response.ok) throw new Error('Failed to fetch tasks')
      return response.json()
    },
    refetchInterval: 10000,
  })

  const successRate = tasks.length > 0
    ? Math.round((tasks.filter(t => t.status === 'SUCCESS').length / tasks.length) * 100)
    : 0

  const avgLatency = tasks.length > 0
    ? Math.round(
        tasks.reduce((sum, task) => {
          if (task.nlm_metadata?.total_token_count) return sum + 1
          return sum
        }, 0) / tasks.length * 100
      )
    : 0

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-gray-900 border border-gray-700 rounded p-4">
        <div className="text-gray-400 text-xs font-semibold uppercase">Success Rate</div>
        <div className="text-3xl font-bold text-green-400 mt-2">{successRate}%</div>
        <div className="text-gray-500 text-xs mt-2">{tasks.filter(t => t.status === 'SUCCESS').length} / {tasks.length}</div>
      </div>
      <div className="bg-gray-900 border border-gray-700 rounded p-4">
        <div className="text-gray-400 text-xs font-semibold uppercase">Tasks Processed</div>
        <div className="text-3xl font-bold text-blue-400 mt-2">{tasks.length}</div>
        <div className="text-gray-500 text-xs mt-2">Total tasks in system</div>
      </div>
    </div>
  )
}

// ============================================================================
// Log Terminal Component
// ============================================================================

const LogTerminal = () => {
  const [logs, setLogs] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const terminalRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//localhost:8000/ws/logs`

    const connectWebSocket = () => {
      try {
        wsRef.current = new WebSocket(wsUrl)

        wsRef.current.onopen = () => {
          setIsConnected(true)
          console.log('WebSocket connected')
        }

        wsRef.current.onmessage = (event) => {
          setLogs((prev) => [...prev, event.data])
          // Auto-scroll to bottom
          if (terminalRef.current) {
            setTimeout(() => {
              terminalRef.current.scrollTop = terminalRef.current.scrollHeight
            }, 0)
          }
        }

        wsRef.current.onerror = (error) => {
          console.error('WebSocket error:', error)
          setIsConnected(false)
        }

        wsRef.current.onclose = () => {
          setIsConnected(false)
          console.log('WebSocket disconnected')
          // Attempt to reconnect
          setTimeout(connectWebSocket, 3000)
        }
      } catch (error) {
        console.error('Failed to connect WebSocket:', error)
        setTimeout(connectWebSocket, 3000)
      }
    }

    connectWebSocket()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const clearLogs = () => {
    setLogs([])
  }

  return (
    <div className="flex flex-col h-full bg-black border border-gray-700 rounded overflow-hidden">
      <div className="flex items-center justify-between bg-gray-900 px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-300">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <button
          onClick={clearLogs}
          className="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded"
        >
          Clear
        </button>
      </div>
      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto bg-black p-4 font-mono text-sm text-green-400"
        style={{ fontFamily: 'Courier New, monospace' }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-600">Waiting for logs...</div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="whitespace-pre-wrap break-words">
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Main App Component
// ============================================================================

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white mb-2">Agent Command Center</h1>
        <p className="text-gray-400">Monitor tasks, metrics, and real-time logs</p>
      </div>

      {/* Metrics Bar */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Metrics</h2>
        <MetricsBar />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tasks Section - Takes 2 columns */}
        <div className="lg:col-span-2">
          <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-gray-200">Task History</h2>
            </div>
            <div className="overflow-x-auto">
              <TaskTable />
            </div>
          </div>
        </div>

        {/* Log Terminal - Takes 1 column */}
        <div className="lg:col-span-1">
          <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden h-full" style={{ minHeight: '500px' }}>
            <div className="px-6 py-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-gray-200">Live Logs</h2>
            </div>
            <LogTerminal />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
