export enum JobStatus {
    PENDING = "pending",
    RUNNING = "running",
    COMPLETE = "complete",
    FAILED = "failed",
    LOST = "lost",
    DEAD = "dead",
    DEGRADED = "degraded",
    BLOCKED = "blocked"
}

export enum AllocationStatus {
    PENDING = "pending",
    RUNNING = "running",
    COMPLETE = "complete",
    FAILED = "failed",
    LOST = "lost",
    STOPPED = "stopped"
}

export interface Task {
    name: string;
    resources: {
        cpu: number;
        memory: number;
    };
    config: {
        command?: string;
        image?: string;
        port?: number;
    };
    status: string;
    start_time: number | null;
    end_time: number | null;
    exit_code?: number;
}

export interface TaskGroup {
    name: string;
    tasks: Task[];
}

export interface Allocation {
    allocation_id: string;
    node_id: string;
    task_group: string;
    status: AllocationStatus;
    start_time: number | null;
    end_time: number | null;
    tasks: Record<string, Task>;
}

export interface Job {
    job_id: string;
    task_groups: TaskGroup[];
    constraints: {
        region: string;
    };
    status: JobStatus;
    allocations: Allocation[];
} 