from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    SUCCESS = "success"
    FAILED = "failed"


TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {
        TaskStatus.PAUSED,
        TaskStatus.STOPPED,
        TaskStatus.SUCCESS,
        TaskStatus.FAILED,
    },
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.STOPPED},
    TaskStatus.STOPPED: set(),
    TaskStatus.SUCCESS: set(),
    TaskStatus.FAILED: set(),
}


def can_transition(current: str, target: str) -> bool:
    current_status = TaskStatus(current)
    target_status = TaskStatus(target)
    return target_status in TASK_TRANSITIONS[current_status]
