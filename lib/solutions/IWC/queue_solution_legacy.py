from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

# LEGACY CODE ASSET
# RESOLVED on deploy
from solutions.IWC.task_types import TaskSubmission, TaskDispatch

class Priority(IntEnum):
    """Represents the queue ordering tiers observed in the legacy system."""
    HIGH = 1
    NORMAL = 2

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
        self._newest_timestamp_cache = None

    def _is_bank_statements_provider(self, task: TaskSubmission) -> bool:
        return task.provider == "bank_statements"
    
    def _user_task_count(self, user_id: int) -> int:
        return sum(1 for task in self._queue if task.user_id == user_id)

    def _bank_statements_sort_key(self, task: TaskSubmission):
        is_bank = self._is_bank_statements_provider(task)
        priority = self._priority_for_task(task)
        task_timestamp = self._timestamp_for_task(task)
        
        group_earliest_raw = self._earliest_group_timestamp_for_task(task)
        if group_earliest_raw == MAX_TIMESTAMP:
            group_timestamp = task_timestamp
        elif isinstance(group_earliest_raw, str):
            group_timestamp = self._timestamp_for_task(TaskSubmission(provider="", user_id=0, timestamp=group_earliest_raw))
        else:
            group_timestamp = group_earliest_raw

        # Check if bank_statements is time-sensitive (5+ minutes old)
        if is_bank and self._newest_timestamp_cache is not None:
            task_age_seconds = (self._newest_timestamp_cache - task_timestamp).total_seconds()
            is_bank_and_old = task_age_seconds >= 300 
        else:
            is_bank_and_old = False

        # Sort Key Structure: (Priority, BankPenalty, GroupTimestamp, TaskTimestamp, TieBreaker)
        
        # 1. Time-based elevation with Rule of 3: Full HIGH priority, no bank penalty
        if is_bank_and_old and priority == Priority.HIGH and group_earliest_raw != MAX_TIMESTAMP:
            return (priority, 0, group_timestamp, task_timestamp, -1)
        
        # 2. Time-based elevation without Rule of 3: Between HIGH and NORMAL
        # Respect timestamp ordering: sort as NORMAL priority but with -1 tiebreaker
        # This way it comes before NORMAL tasks with same timestamp but after NORMAL tasks with older timestamps
        if is_bank_and_old:
            return (Priority.NORMAL, 0, group_timestamp, task_timestamp, -1)
        
        # 3. Rule of 3 elevation: Treat high priority bank statements as high priority, 
        # but apply penalty to put them after other high priority tasks of the same user.
        if is_bank and priority == Priority.HIGH and group_earliest_raw != MAX_TIMESTAMP:
            return (priority, 1, group_timestamp, task_timestamp, 0)
        
        # 4. Standard Bank Statement: Deprioritized (Priority 3)
        elif is_bank:
            return (3, 1, task_timestamp, task_timestamp, 0)
        
        # 5. All other tasks
        else:
            return (priority, 0, group_timestamp, task_timestamp, 0)
    
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

    def _update_priorities(self):
        if not self._queue:
            return
            
        # First calculate user stats
        user_ids = {task.user_id for task in self._queue}
        task_count = {}
        priority_timestamps = {}
        
        for user_id in user_ids:
            user_tasks = [t for t in self._queue if t.user_id == user_id]
            earliest_timestamp = sorted(user_tasks, key=lambda t: self._timestamp_for_task(t))[0].timestamp
            priority_timestamps[user_id] = earliest_timestamp
            task_count[user_id] = len(user_tasks)

        # Cache newest timestamp for age calculations
        self._newest_timestamp_cache = max(self._timestamp_for_task(t) for t in self._queue)

        # Update metadata for all tasks
        for task in self._queue:
            metadata = task.metadata

            # Rule of 3 Application
            if task_count[task.user_id] >= 3:
                metadata["priority"] = Priority.HIGH
                metadata["group_earliest_timestamp"] = priority_timestamps[task.user_id]
            else:
                metadata["priority"] = Priority.NORMAL
                metadata["group_earliest_timestamp"] = MAX_TIMESTAMP

    def enqueue(self, item: TaskSubmission) -> int:
        tasks = [*self._collect_dependencies(item), item]

        for task in tasks:
            # check for duplicates
            duplicate_index = next(
                (i for i, t in enumerate(self._queue)
                 if t.provider == task.provider and t.user_id == task.user_id),
                None)
            if duplicate_index is not None:
                exisiting_task = self._queue[duplicate_index]
                # Keep the earliest timestamp
                if self._timestamp_for_task(task) < self._timestamp_for_task(exisiting_task):
                    task.metadata = exisiting_task.metadata 
                    self._queue[duplicate_index] = task
            else:
                metadata = task.metadata
                metadata.setdefault("priority", Priority.NORMAL)
                metadata.setdefault("group_earliest_timestamp", MAX_TIMESTAMP)
                self._queue.append(task)
        
        return self.size

    def dequeue(self):
        if self.size == 0:
            return None

        self._update_priorities()
        self._queue.sort(key=self._bank_statements_sort_key)

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
        if self.size == 0:
            return 0
        timestamps = [self._timestamp_for_task(task) for task in self._queue]
        oldest_timestamp = min(timestamps)
        newest_timestamp = max(timestamps)
        return (newest_timestamp - oldest_timestamp).total_seconds()

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
