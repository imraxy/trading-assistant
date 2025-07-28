"""
Progress Tracker Service - Real-time task progress tracking
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ProgressUpdate:
    """Single progress update"""
    task_id: str
    step: str
    progress: float  # 0.0 to 1.0
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class TaskProgress:
    """Complete task progress information"""
    task_id: str
    name: str
    status: str  # 'running', 'completed', 'error', 'cancelled'
    progress: float  # 0.0 to 1.0
    current_step: str
    total_steps: int
    completed_steps: int
    started_at: str
    completed_at: Optional[str] = None
    updates: List[ProgressUpdate] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.updates is None:
            self.updates = []

class ProgressTracker:
    """Global progress tracking service"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskProgress] = {}
        self.max_updates_per_task = 50  # Keep last 50 updates
    
    def start_task(self, task_id: str, name: str, total_steps: int = 100) -> TaskProgress:
        """Start tracking a new task"""
        task = TaskProgress(
            task_id=task_id,
            name=name,
            status='running',
            progress=0.0,
            current_step='Starting...',
            total_steps=total_steps,
            completed_steps=0,
            started_at=datetime.utcnow().isoformat(),
            updates=[]
        )
        self.tasks[task_id] = task
        
        logger.info(f"📊 Started tracking task: {name} ({task_id})")
        return task
    
    def update_progress(
        self,
        task_id: str,
        step: str,
        progress: float = None,
        message: str = None,
        details: Dict[str, Any] = None,
        extra_data: Dict[str, Any] = None
    ):
        """Update task progress"""
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found for progress update")
            return
        
        task = self.tasks[task_id]
        
        # Update task info
        task.current_step = step
        if progress is not None:
            task.progress = max(0.0, min(1.0, progress))  # Clamp between 0-1
            task.completed_steps = int(task.progress * task.total_steps)
        
        # Merge extra_data into details
        combined_details = details or {}
        if extra_data:
            combined_details.update(extra_data)
        
        # Create progress update
        update = ProgressUpdate(
            task_id=task_id,
            step=step,
            progress=task.progress,
            message=message or step,
            timestamp=datetime.utcnow().isoformat(),
            details=combined_details
        )
        
        # Add to updates list (keep only recent ones)
        task.updates.append(update)
        if len(task.updates) > self.max_updates_per_task:
            task.updates = task.updates[-self.max_updates_per_task:]
        
        logger.info(f"📈 {task.name}: {step} ({task.progress:.1%})")
    
    def complete_task(self, task_id: str, message: str = "Completed successfully"):
        """Mark task as completed"""
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found for completion")
            return
        
        task = self.tasks[task_id]
        task.status = 'completed'
        task.progress = 1.0
        task.completed_steps = task.total_steps
        task.current_step = 'Completed'
        task.completed_at = datetime.utcnow().isoformat()
        
        # Add final update
        self.update_progress(task_id, 'Completed', 1.0, message)
        
        logger.info(f"✅ Completed task: {task.name} ({task_id})")
    
    def error_task(self, task_id: str, error: str):
        """Mark task as failed"""
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found for error")
            return
        
        task = self.tasks[task_id]
        task.status = 'error'
        task.current_step = 'Failed'
        task.completed_at = datetime.utcnow().isoformat()
        task.error = error
        
        # Add error update
        self.update_progress(task_id, 'Failed', task.progress, f"Error: {error}")
        
        logger.error(f"❌ Task failed: {task.name} ({task_id}) - {error}")
    
    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Get task progress"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskProgress]:
        """Get all tasks"""
        return list(self.tasks.values())
    
    def get_active_tasks(self) -> List[TaskProgress]:
        """Get only running tasks"""
        return [task for task in self.tasks.values() if task.status == 'running']
    
    def get_recent_updates(self, task_id: str, limit: int = 10) -> List[ProgressUpdate]:
        """Get recent updates for a task"""
        task = self.tasks.get(task_id)
        if not task:
            return []
        return task.updates[-limit:]
    
    def get_latest_data(self, task_id: str, key: str = None) -> Any:
        """Get the latest extra data from a task's most recent update"""
        task = self.tasks.get(task_id)
        if not task or not task.updates:
            return None
        
        latest_update = task.updates[-1]
        if not latest_update.details:
            return None
        
        if key:
            return latest_update.details.get(key)
        return latest_update.details
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for task_id, task in self.tasks.items():
            if task.status in ['completed', 'error', 'cancelled']:
                if task.completed_at:
                    task_time = datetime.fromisoformat(task.completed_at).timestamp()
                    if task_time < cutoff_time:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
            logger.info(f"🧹 Cleaned up old task: {task_id}")
    
    def to_dict(self, task_id: str = None) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        if task_id:
            task = self.tasks.get(task_id)
            return asdict(task) if task else {}
        
        return {
            'tasks': [asdict(task) for task in self.tasks.values()],
            'active_count': len(self.get_active_tasks()),
            'total_count': len(self.tasks)
        }

# Global instance
progress_tracker = ProgressTracker()

def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance"""
    return progress_tracker 