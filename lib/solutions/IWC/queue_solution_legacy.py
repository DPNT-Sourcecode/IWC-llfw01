from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

# LEGACY CODE ASSET
# RESOLVED on deploy
from solutions.IWC.task_types import TaskSubmission, TaskDispatch

class Priority(IntEnum):
    """Represents the queue ordering tiers observed in the legacy system."""
    HIGH = 1  # Rule of 3
    NORMAL = 2  # Normal tasks

@dataclass
class Provider:
    name: str
    base_url: str
    depends_on: list[str]

MAX_TIMESTAMP = datetime.max.replace(tzinfo=None)

COMPANIES_HOUSE_PROVIDER = Provider(
    name="companies_house", base_url="https://fake.companieshouse.co.uk", depends_on=[]
)


CREDIT_CHECK_PROVIDER = Provider(
    name="credit_check",
    base_url="https://fake.creditcheck.co.uk",
    depends_on=["companies_house"],
)


BANK_STATEMENTS_PROVIDER = Provider(
    name="bank_statements", base_url="https://fake.bankstatements.co.uk", depends_on=[]
)

ID_VERIFICATION_PROVIDER = Provider(
    name="id_verification", base_url="https://fake.idv.co.uk", depends_on=[]
)


REGISTERED_PROVIDERS: list[Provider] = [
    BANK_STATEMENTS_PROVIDER,
    COMPANIES_HOUSE_PROVIDER,
    CREDIT_CHECK_PROVIDER,
    ID_VERIFICATION_PROVIDER,
]

class Queue:
    def __init__(self):
        self._queue = []
    
    def _collect_dependencies(self, task: TaskSubmission) -> list[TaskSubmission]:
        provider = next((p for p in REGISTERED_PROVIDERS if p.name == task.provider), None)
        if provider is None:
            return []

        tasks: list[TaskSubmission] = []
        for dependency in provider.depends_on:
            dependency_task = TaskSubmission(
                provider=dependency,
                user_id=task.user_id,
                timestamp=task.timestamp,
            )
            tasks.extend(self._collect_dependencies(dependency_task))
            tasks.append(dependency_task)
        return tasks

    @staticmethod
    def _priority_for_task(task):
        metadata = task.metadata
        raw_priority = metadata.get("priority", Priority.NORMAL)
        try:
            return Priority(raw_priority)
        except (TypeError, ValueError):
            return Priority.NORMAL

    @staticmethod
    def _earliest_group_timestamp_for_task(task):
        metadata = task.metadata
        return metadata.get("group_earliest_timestamp", MAX_TIMESTAMP)

    @staticmethod
    def _timestamp_for_task(task):
        timestamp = task.timestamp
        if isinstance(timestamp, datetime):
            return timestamp.replace(tzinfo=None)
        if isinstance(timestamp, str):
            return datetime.fromisoformat(timestamp).replace(tzinfo=None)
        return timestamp

    @staticmethod
    def _is_bank_statements(task):
        """Returns 1 if task is bank_statements (to deprioritize), 0 otherwise."""
        return 1 if task.provider == "bank_statements" else 0

    @staticmethod
    def _deprioritization_key(task):
        """
        Returns deprioritization value for sorting.
        - 0: Not bank_statements (normal priority)
        - 0: bank_statements but time-sensitive (not deprioritized)
        - 1: bank_statements and not time-sensitive (deprioritized)
        """
        if task.provider != "bank_statements":
            return 0
        
        # Check if this bank_statements task is time-sensitive
        is_time_sensitive = task.metadata.get("is_time_sensitive", False)
        if is_time_sensitive:
            return 0  # Don't deprioritize
        else:
            return 1  # Deprioritize

    def enqueue(self, item: TaskSubmission) -> int:
        tasks = [*self._collect_dependencies(item), item]

        for task in tasks:
            # Check for duplicate (user_id, provider) pair
            existing_task = None
            for i, queued_task in enumerate(self._queue):
                if queued_task.user_id == task.user_id and queued_task.provider == task.provider:
                    existing_task = (i, queued_task)
                    break
            
            if existing_task is not None:
                # Duplicate found - keep the one with older timestamp
                idx, queued_task = existing_task
                new_timestamp = self._timestamp_for_task(task)
                existing_timestamp = self._timestamp_for_task(queued_task)
                
                if new_timestamp < existing_timestamp:
                    # New task has older timestamp, replace the existing one
                    self._queue[idx] = task
                    metadata = task.metadata
                    metadata.setdefault("priority", Priority.NORMAL)
                    metadata.setdefault("group_earliest_timestamp", MAX_TIMESTAMP)
                # else: existing task has older timestamp, ignore the new one
            else:
                # No duplicate, add the new task
                metadata = task.metadata
                metadata.setdefault("priority", Priority.NORMAL)
                metadata.setdefault("group_earliest_timestamp", MAX_TIMESTAMP)
                self._queue.append(task)
        return self.size

    def dequeue(self):
        if self.size == 0:
            return None

        user_ids = {task.user_id for task in self._queue}
        task_count = {}
        priority_timestamps = {}
        for user_id in user_ids:
            user_tasks = [t for t in self._queue if t.user_id == user_id]
            earliest_task = sorted(user_tasks, key=lambda t: self._timestamp_for_task(t))[0]
            priority_timestamps[user_id] = self._timestamp_for_task(earliest_task)
            task_count[user_id] = len(user_tasks)

        # Determine which bank_statements tasks are time-sensitive
        # A bank_statements task is time-sensitive if there are tasks 5+ minutes newer
        TIME_SENSITIVE_THRESHOLD = 300  # 5 minutes in seconds
        time_sensitive_tasks = set()
        
        for task in self._queue:
            if task.provider == "bank_statements":
                task_timestamp = self._timestamp_for_task(task)
                # Check if any task is 5+ minutes newer
                for other_task in self._queue:
                    other_timestamp = self._timestamp_for_task(other_task)
                    time_diff = (other_timestamp - task_timestamp).total_seconds()
                    if time_diff >= TIME_SENSITIVE_THRESHOLD:
                        time_sensitive_tasks.add(id(task))
                        break

        for task in self._queue:
            metadata = task.metadata
            current_earliest = metadata.get("group_earliest_timestamp", MAX_TIMESTAMP)
            raw_priority = metadata.get("priority")
            try:
                priority_level = Priority(raw_priority)
            except (TypeError, ValueError):
                priority_level = None

            # Check if task is time-sensitive
            is_time_sensitive = id(task) in time_sensitive_tasks
            
            if priority_level is None or priority_level == Priority.NORMAL:
                if task_count[task.user_id] >= 3:
                    # Rule of 3 priority
                    metadata["group_earliest_timestamp"] = priority_timestamps[task.user_id]
                    metadata["priority"] = Priority.HIGH
                else:
                    # Normal priority - all tasks use MAX_TIMESTAMP for group sorting
                    metadata["priority"] = Priority.NORMAL
                    metadata["group_earliest_timestamp"] = MAX_TIMESTAMP
            else:
                metadata["group_earliest_timestamp"] = current_earliest
                metadata["priority"] = priority_level
            
            # Mark time-sensitive bank_statements
            metadata["is_time_sensitive"] = is_time_sensitive

        self._queue.sort(
            key=lambda i: (
                self._priority_for_task(i),
                self._earliest_group_timestamp_for_task(i),
                self._deprioritization_key(i),  # Smart deprioritization - returns 0 for time-sensitive
                self._timestamp_for_task(i),
                # Tie-breaker: time-sensitive bank_statements come first when timestamps are equal
                0 if (i.provider == "bank_statements" and i.metadata.get("is_time_sensitive", False)) else 1,
            )
        )

        task = self._queue.pop(0)
        return TaskDispatch(
            provider=task.provider,
            user_id=task.user_id,
        )

    @property
    def size(self):
        return len(self._queue)

    @property
    def age(self):
        """
        Returns the time gap in seconds between the oldest and newest tasks in the queue.
        Returns 0 if the queue is empty or has only one task.
        """
        if len(self._queue) <= 1:
            return 0
        
        timestamps = [self._timestamp_for_task(task) for task in self._queue]
        oldest = min(timestamps)
        newest = max(timestamps)
        
        time_diff = newest - oldest
        return int(time_diff.total_seconds())

    def purge(self):
        self._queue.clear()
        return True

"""
===================================================================================================

The following code is only to visualise the final usecase.
No changes are needed past this point.

To test the correct behaviour of the queue system, import the `Queue` class directly in your tests.

===================================================================================================

```python
import asyncio
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(queue_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Queue worker cancelled on shutdown.")


app = FastAPI(lifespan=lifespan)
queue = Queue()


@app.get("/")
def read_root():
    return {
        "registered_providers": [
            {"name": p.name, "base_url": p.base_url} for p in registered_providers
        ]
    }


class DataRequest(BaseModel):
    user_id: int
    providers: list[str]


@app.post("/fetch_customer_data")
def fetch_customer_data(data: DataRequest):
    provider_names = [p.name for p in registered_providers]

    for provider in data.providers:
        if provider not in provider_names:
            logger.warning(f"Provider {provider} doesn't exists. Skipping")
            continue

        queue.enqueue(
            TaskSubmission(
                provider=provider,
                user_id=data.user_id,
                timestamp=datetime.now(),
            )
        )

    return {"status": f"{len(data.providers)} Task(s) added to queue"}


async def queue_worker():
    while True:
        if queue.size == 0:
            await asyncio.sleep(1)
            continue

        task = queue.dequeue()
        if not task:
            continue

        logger.info(f"Processing task: {task}")
        await asyncio.sleep(2)
        logger.info(f"Finished task: {task}")
```
"""





