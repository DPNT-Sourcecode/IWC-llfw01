import sys
sys.path.insert(0, 'lib')
from solutions.IWC.queue_solution_legacy import Queue
from solutions.IWC.task_types import TaskSubmission

def iso_ts(delta_minutes):
    from datetime import datetime, timedelta
    base = datetime(2025, 10, 20, 12, 0, 0)
    return (base + timedelta(minutes=delta_minutes)).strftime('%Y-%m-%d %H:%M:%S')

# Test IWC_R5_S6
queue = Queue()
print("Test IWC_R5_S6:")
print("1. Enqueue bank_statements, user 1, 12:00:00")
queue.enqueue(TaskSubmission(provider="bank_statements", user_id=1, timestamp=iso_ts(0)))
print("2. Enqueue companies_house, user 2, 12:01:00")
queue.enqueue(TaskSubmission(provider="companies_house", user_id=2, timestamp=iso_ts(1)))
print("3. Enqueue id_verification, user 2, 12:06:00")
queue.enqueue(TaskSubmission(provider="id_verification", user_id=2, timestamp=iso_ts(6)))
print("4. Enqueue bank_statements, user 2, 12:07:00")
queue.enqueue(TaskSubmission(provider="bank_statements", user_id=2, timestamp=iso_ts(7)))

print("\nQueue state:")
queue._update_priorities()
for i, task in enumerate(queue._queue):
    print(f"  {i}: {task.provider}, user {task.user_id}, {task.timestamp}, priority={task.metadata.get('priority')}")

print("\nDequeuing:")
for i in range(4):
    result = queue.dequeue()
    print(f"  {i+1}. {result.provider}, user {result.user_id}")

print("\n" + "="*50)
print("\nTest IWC_R5_S7:")
queue2 = Queue()
print("1. companies_house, user 2, 12:00:00")
queue2.enqueue(TaskSubmission(provider="companies_house", user_id=2, timestamp=iso_ts(0)))
print("2. bank_statements, user 1, 12:01:00")
queue2.enqueue(TaskSubmission(provider="bank_statements", user_id=1, timestamp=iso_ts(1)))
print("3. id_verification, user 2, 12:02:00")
queue2.enqueue(TaskSubmission(provider="id_verification", user_id=2, timestamp=iso_ts(2)))
print("4. bank_statements, user 2, 12:07:00")
queue2.enqueue(TaskSubmission(provider="bank_statements", user_id=2, timestamp=iso_ts(7)))
print("5. companies_house, user 1, 12:08:00")
queue2.enqueue(TaskSubmission(provider="companies_house", user_id=1, timestamp=iso_ts(8)))
print("6. id_verification, user 1, 12:09:00")
queue2.enqueue(TaskSubmission(provider="id_verification", user_id=1, timestamp=iso_ts(9)))

print("\nQueue state:")
queue2._update_priorities()
for i, task in enumerate(queue2._queue):
    ts = queue2._timestamp_for_task(task)
    age = (queue2._newest_timestamp_cache - ts).total_seconds() if queue2._newest_timestamp_cache else 0
    print(f"  {i}: {task.provider}, user {task.user_id}, {task.timestamp}, priority={task.metadata.get('priority')}, age={age}s")

print("\nDequeuing:")
for i in range(6):
    print(f"Queue size before dequeue: {queue2.size}")
    if queue2.size == 0:
        print("  Queue is empty!")
        break
    try:
        result = queue2.dequeue()
        if result:
            print(f"  {i+1}. {result.provider}, user {result.user_id}")
        else:
            print(f"  {i+1}. None returned!")
    except Exception as e:
        print(f"  {i+1}. ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\nTest complete!")

