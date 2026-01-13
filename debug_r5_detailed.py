import sys
sys.path.insert(0, 'lib')

from solutions.IWC.queue_solution_legacy import Queue
from solutions.IWC.task_types import TaskSubmission

q = Queue()
q.enqueue(TaskSubmission('id_verification', 1, '2025-01-01 12:00:00'))
q.enqueue(TaskSubmission('bank_statements', 2, '2025-01-01 12:01:00'))
q.enqueue(TaskSubmission('companies_house', 3, '2025-01-01 12:07:00'))

# Manually replicate what dequeue does
print('FIRST DEQUEUE:')
print('Queue before sort:')
for t in q._queue:
    print(f'  {t.provider:20s} pri={t.metadata.get("priority")}')

# Sort happens
q._queue.sort(key=q._bank_statements_sort_key)

print('\nQueue after sort:')
for i, t in enumerate(q._queue):
    print(f'  [{i}] {t.provider:20s}')

print(f'\nPopping: {q._queue[0].provider}')
q._queue.pop(0)

print('\n\nSECOND DEQUEUE:')
# Update priorities for Rule of 3
user_ids = {task.user_id for task in q._queue}
task_count = {}
for user_id in user_ids:
    user_tasks = [t for t in q._queue if t.user_id == user_id]
    task_count[user_id] = len(user_tasks)

for task in q._queue:
    if task_count[task.user_id] >= 3:
        task.metadata["priority"] = 1  # HIGH
    else:
        task.metadata["priority"] = 2  # NORMAL

print('Queue before sort:')
for t in q._queue:
    print(f'  {t.provider:20s} pri={t.metadata.get("priority")}')

# Check sort keys BEFORE sorting
print('\nSort keys before sorting:')
for t in q._queue:
    key = q._bank_statements_sort_key(t)
    print(f'  {t.provider:20s}: {key}')

# Sort happens
q._queue.sort(key=q._bank_statements_sort_key)

print('\nQueue after sort:')
for i, t in enumerate(q._queue):
    print(f'  [{i}] {t.provider:20s}')
