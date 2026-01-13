import sys
sys.path.insert(0, 'lib')

from solutions.IWC.queue_solution_legacy import Queue
from solutions.IWC.task_types import TaskSubmission

q = Queue()
q.enqueue(TaskSubmission('id_verification', 1, '2025-01-01 12:00:00'))
q.enqueue(TaskSubmission('bank_statements', 2, '2025-01-01 12:01:00'))
q.enqueue(TaskSubmission('companies_house', 3, '2025-01-01 12:07:00'))

print('Initial queue - before calling dequeue():')
for t in q._queue:
    key = q._bank_statements_sort_key(t)
    print(f'  {t.provider:20s}: {key}')

# Now let's trace through the ACTUAL dequeue call to see what happens
print('\n\nCalling dequeue()...')
result = q.dequeue()
print(f'Result: {result}')

print('\n\nRemaining queue:')
for t in q._queue:
    print(f'  {t.provider}')
