import sys
sys.path.insert(0, 'lib')

from solutions.IWC.queue_solution_legacy import Queue
from solutions.IWC.task_types import TaskSubmission
from datetime import datetime

q = Queue()
q.enqueue(TaskSubmission('id_verification', 1, '2025-01-01 12:00:00'))
q.enqueue(TaskSubmission('bank_statements', 2, '2025-01-01 12:01:00'))
q.enqueue(TaskSubmission('companies_house', 3, '2025-01-01 12:07:00'))

print('Queue after enqueue:')
for t in q._queue:
    ts = q._timestamp_for_task(t)
    print(f'  {t.provider}, user {t.user_id}, ts {ts}')

print('\nChecking bank_statements age:')
bank_task = [t for t in q._queue if t.provider == 'bank_statements'][0]
newest = max(q._timestamp_for_task(t) for t in q._queue)
bank_ts = q._timestamp_for_task(bank_task)
age = (newest - bank_ts).total_seconds()
print(f'  bank_statements ts: {bank_ts}')
print(f'  newest ts: {newest}')
print(f'  age: {age} seconds')
print(f'  is >= 300: {age >= 300}')

print('\nDequeue 1:', q.dequeue())
print('\nQueue after 1st dequeue:')
for t in q._queue:
    ts = q._timestamp_for_task(t)
    pri = t.metadata.get('priority')
    print(f'  {t.provider}, user {t.user_id}, ts {ts}, priority={pri}')

print('\nDequeue 2:', q.dequeue())
print('\nDequeue 3:', q.dequeue())
