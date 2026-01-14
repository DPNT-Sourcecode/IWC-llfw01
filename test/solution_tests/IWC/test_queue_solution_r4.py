from __future__ import annotations

from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def call_age():
    """Helper to call the age() method on the queue."""
    from .utils import QueueActionBuilder
    return QueueActionBuilder("age")


def test_age_example_from_spec() -> None:
    """
    Example from IWC_R4.txt - Queue Internal Age:
    5 minutes gap between oldest and newest task = 300 seconds.
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="id_verification", timestamp='2025-10-20 12:00:00' -> 1
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        # 2. Enqueue: user_id=2, provider="id_verification", timestamp='2025-10-20 12:05:00' -> 2
        call_enqueue("id_verification", 2, "2025-10-20 12:05:00").expect(2),
        # 3. Age -> 300 (5 minutes)
        call_age().expect(300),
    ])


def test_age_empty_queue() -> None:
    """
    Age should return 0 for an empty queue.
    """
    run_queue([
        call_age().expect(0),
    ])


def test_age_single_task() -> None:
    """
    Age should return 0 when there's only one task (no gap).
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_age().expect(0),
    ])


def test_age_updates_with_new_tasks() -> None:
    """
    Age should update as new tasks are added.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        call_age().expect(0),
        # Add task 10 minutes later
        call_enqueue("companies_house", 2, "2025-10-20 12:10:00").expect(2),
        call_age().expect(600),  # 10 minutes = 600 seconds
        # Add task 5 minutes after first
        call_enqueue("bank_statements", 3, "2025-10-20 12:05:00").expect(3),
        call_age().expect(600),  # Still 10 minutes (from 12:00 to 12:10)
    ])


def test_age_after_dequeue() -> None:
    """
    Age should update after dequeue operations.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("id_verification", 2, "2025-10-20 12:10:00").expect(2),
        call_enqueue("companies_house", 3, "2025-10-20 12:15:00").expect(3),
        call_age().expect(900),  # 15 minutes
        # Dequeue one task
        call_dequeue().expect("companies_house", 1),
        call_age().expect(300),  # Now 5 minutes (12:10 to 12:15)
        # Dequeue another
        call_dequeue().expect("id_verification", 2),
        call_age().expect(0),  # Only one task left
    ])


def test_age_becomes_zero_when_emptied() -> None:
    """
    Age should return 0 after all tasks are dequeued.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:20:00").expect(2),
        call_age().expect(1200),  # 20 minutes
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 2),
        call_age().expect(0),
    ])


def test_age_with_deduplication() -> None:
    """
    Age should work correctly with deduplication.
    When a duplicate is removed, age calculation should use remaining tasks.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:10:00").expect(2),
        call_age().expect(600),  # 10 minutes
        # Duplicate with newer timestamp (will be ignored, older kept)
        call_enqueue("bank_statements", 1, "2025-10-20 12:20:00").expect(2),
        call_age().expect(600),  # Still 10 minutes (12:00 to 12:10)
        # Duplicate with older timestamp (will replace existing)
        call_enqueue("companies_house", 2, "2025-10-20 12:05:00").expect(2),
        call_age().expect(300),  # Now 5 minutes (12:00 to 12:05)
    ])


def test_age_with_dependencies() -> None:
    """
    Age should account for dependency tasks added automatically.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_age().expect(0),
        # credit_check depends on companies_house
        # Both tasks added with same timestamp
        call_enqueue("credit_check", 2, "2025-10-20 12:10:00").expect(3),
        call_age().expect(600),  # 10 minutes (12:00 to 12:10)
    ])


def test_age_large_time_gap() -> None:
    """
    Age should handle large time gaps correctly.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 08:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 18:30:00").expect(2),
        call_age().expect(37800),  # 10.5 hours = 37800 seconds
    ])


def test_age_with_same_timestamps() -> None:
    """
    Age should return 0 when all tasks have the same timestamp.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:00:00").expect(2),
        call_enqueue("bank_statements", 3, "2025-10-20 12:00:00").expect(3),
        call_age().expect(0),
    ])


def test_age_with_rule_of_3() -> None:
    """
    Age should work correctly when Rule of 3 is triggered.
    It's based on task timestamps, not processing order.
    """
    run_queue([
        # User 1 will trigger Rule of 3
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("id_verification", 1, "2025-10-20 12:05:00").expect(2),
        call_enqueue("bank_statements", 1, "2025-10-20 12:10:00").expect(3),
        # User 2
        call_enqueue("companies_house", 2, "2025-10-20 12:15:00").expect(4),
        call_age().expect(900),  # 15 minutes from oldest to newest
    ])


def test_age_after_purge() -> None:
    """
    Age should return 0 after queue is purged.
    """
    from solutions.IWC.queue_solution_entrypoint import QueueSolutionEntrypoint
    queue = QueueSolutionEntrypoint()
    
    from solutions.IWC.task_types import TaskSubmission
    queue.enqueue(TaskSubmission(provider="companies_house", user_id=1, timestamp="2025-10-20 12:00:00"))
    queue.enqueue(TaskSubmission(provider="id_verification", user_id=2, timestamp="2025-10-20 12:30:00"))
    
    assert queue.age() == 1800, "Age should be 1800 seconds (30 minutes)"
    
    queue.purge()
    assert queue.age() == 0, "Age should be 0 after purge"


def test_age_complex_scenario() -> None:
    """
    Complex scenario testing age calculation through various operations.
    Gaps < 5 min to avoid time-sensitive behavior affecting test logic.
    """
    run_queue([
        # Start with 3 tasks over 4 minutes
        call_enqueue("companies_house", 1, "2025-10-20 10:00:00").expect(1),
        call_enqueue("id_verification", 2, "2025-10-20 10:02:00").expect(2),
        call_enqueue("bank_statements", 3, "2025-10-20 10:04:00").expect(3),
        call_age().expect(240),  # 4 minutes
        
        # Add task in the middle (doesn't change age)
        call_enqueue("companies_house", 4, "2025-10-20 10:03:00").expect(4),
        call_age().expect(240),  # Still 4 minutes
        
        # Dequeue oldest (companies_house user 1)
        call_dequeue().expect("companies_house", 1),
        call_age().expect(120),  # Now 2 minutes (10:02 to 10:04)
        
        # Add newer task (but still < 5 min gap)
        call_enqueue("id_verification", 5, "2025-10-20 10:05:00").expect(4),
        call_age().expect(180),  # 3 minutes (10:02 to 10:05)
        
        # Dequeue all non-bank_statements
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("companies_house", 4),
        call_dequeue().expect("id_verification", 5),
        call_age().expect(0),  # Only bank_statements left
    ])


def test_age_with_millisecond_precision() -> None:
    """
    Age should handle timestamps with high precision.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:00:05").expect(2),
        call_age().expect(5),  # 5 seconds
    ])
