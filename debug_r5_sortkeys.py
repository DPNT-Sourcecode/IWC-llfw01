import sys
sys.path.insert(0, 'lib')

from solutions.IWC.queue_solution_legacy import Queue
from solutions.IWC.task_types import TaskSubmission

q = Queue()
q.enqueue(TaskSubmission('id_verification', 1, '2025-01-01 12:00:00'))
q.enqueue(TaskSubmission('bank_statements', 2, '2025-01-01 12:01:00'))
q.enqueue(TaskSubmission('companies_house', 3, '2025-01-01 12:07:00'))

print('Before dequeue - Sort keys:')
for t in q._queue:
    key = q._bank_statements_sort_key(t)
    print(f'  {t.provider:20s} user {t.user_id}: {key}')

result1 = q.dequeue()
print(f'\nDequeued: {result1}')

print('\nAfter 1st dequeue - Sort keys:')
for t in q._queue:
    key = q._bank_statements_sort_key(t)
    print(f'  {t.provider:20s} user {t.user_id}: {key}')

result2 = q.dequeue()
print(f'\nDequeued: {result2}')
