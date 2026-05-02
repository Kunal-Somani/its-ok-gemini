import { API_BASE } from '../config';

export interface TaskRecord {
    id: string;
    task_name: string;
    status: string;
    email: string;
    round_index: number;
    nonce: string;
    pages_url?: string;
    repo_url?: string;
    commit_sha?: string;
    completed_at?: string;
    duration_seconds?: number;
    created_at: string;
    error_log?: string;
    celery_task_id?: string;
    retry_count?: number;
    step_timestamps?: Record<string, string>;
    step_durations?: Record<string, string>;
}

export const getHeaders = () => {
    const apiKey = localStorage.getItem('API_KEY') || '';
    return {
        'Content-Type': 'application/json',
        'X-Api-Key': apiKey
    };
};

export const getTasks = async (): Promise<TaskRecord[]> => {
    const response = await fetch(`${API_BASE}/api/v1/tasks`, {
        headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch tasks');
    return response.json();
};

export const getTask = async (id: string): Promise<TaskRecord> => {
    const response = await fetch(`${API_BASE}/api/v1/tasks/${id}`, {
        headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch task');
    return response.json();
};

export const getTaskStatus = async (id: string): Promise<TaskRecord> => {
    const response = await fetch(`${API_BASE}/api/v1/tasks/${id}`, {
        headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to fetch task status');
    return response.json();
};

export const createTask = async (payload: { instruction: string; email: string; github_username: string }) => {
    const response = await fetch(`${API_BASE}/api/v1/tasks`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error('Failed to create task');
    return response.json();
};

export const cancelTask = async (id: string) => {
    const response = await fetch(`${API_BASE}/api/v1/tasks/${id}`, {
        method: 'DELETE',
        headers: getHeaders()
    });
    if (!response.ok) throw new Error('Failed to cancel task');
    return true;
};
