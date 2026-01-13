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

    def _is_bank_statements_provider(self, task: TaskSubmission) -> bool:
        return task.provider == "bank_statements"
    
    def _user_task_count(self, user_id: int) -> int:
        return sum(1 for task in self._queue if task.user_id == user_id)

    def _bank_statements_sort_key(self, task: TaskSubmission):
        is_bank = self._is_bank_statements_provider(task)
        user_task_count = self._user_task_count(task.user_id)
        # For users with <3 tasks, bank_statements must be globally last
        if is_bank and user_task_count < 3:
            # Globally deprioritize
            return (2, self._timestamp_for_task(task))
        elif is_bank and user_task_count >= 3:
            # Deprioritize within user's tasks, but still respect Rule of 3
            return (1, self._priority_for_task(task), self._earliest_group_timestamp_for_task(task), self._timestamp_for_task(task))
        else:
            # Normal tasks
            return (0, self._priority_for_task(task), self._earliest_group_timestamp_for_task(task), self._timestamp_for_task(task))
    
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
                    self._queue[duplicate_index] = task
                continue
            else:
                metadata = task.metadata
                metadata.setdefault("priority", Priority.NORMAL)
                metadata.setdefault("group_earliest_timestamp", MAX_TIMESTAMP)
                self._queue.append(task)
        return self.size

def dequeue(self):
    if self.size == 0:
        return None

    # Update metadata for Rule of 3 and priorities
    user_ids = {task.user_id for task in self._queue}
    task_count = {}
    priority_timestamps = {}
    for user_id in user_ids:
        user_tasks = [t for t in self._queue if t.user_id == user_id]
        earliest_timestamp = sorted(user_tasks, key=lambda t: self._timestamp_for_task(t))[0].timestamp
        priority_timestamps[user_id] = earliest_timestamp
        task_count[user_id] = len(user_tasks)

    for task in self._queue:
        metadata = task.metadata
        current_earliest = metadata.get("group_earliest_timestamp", MAX_TIMESTAMP)
        raw_priority = metadata.get("priority")
        try:
            priority_level = Priority(raw_priority)
        except (TypeError, ValueError):
            priority_level = None

        if priority_level is None or priority_level == Priority.NORMAL:
            metadata["group_earliest_timestamp"] = MAX_TIMESTAMP
            if task_count[task.user_id] >= 3:
                metadata["group_earliest_timestamp"] = priority_timestamps[task.user_id]
                metadata["priority"] = Priority.HIGH
            else:
                metadata["priority"] = Priority.NORMAL
        else:
            metadata["group_earliest_timestamp"] = current_earliest
            metadata["priority"] = priority_level

        # Sort with the new deprioritization logic
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
        return 0

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



