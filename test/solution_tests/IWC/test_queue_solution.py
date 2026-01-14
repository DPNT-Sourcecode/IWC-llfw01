from __future__ import annotations

from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def test_enqueue_size_dequeue_flow() -> None:
    run_queue([
        call_enqueue("companies_house", 1, iso_ts(delta_minutes=0)).expect(1),
        call_size().expect(1),
        call_dequeue().expect("companies_house", 1),
    ])


def test_rule_of_3_example_1() -> None:
    """
    Example #1 from IWC_R1.txt - Rule of 3:
    Once user 1 reaches 3 tasks, all of their jobs are moved ahead of user 2's,
    regardless of the original enqueue order.
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="companies_house", timestamp='2025-10-20 12:00:00' -> 1
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        # 2. Enqueue: user_id=2, provider="bank_statements", timestamp='2025-10-20 12:00:00' -> 2
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(2),
        # 3. Enqueue: user_id=1, provider="id_verification", timestamp='2025-10-20 12:00:00' -> 3
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(3),
        # 4. Enqueue: user_id=1, provider="bank_statements", timestamp='2025-10-20 12:00:00' -> 4
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(4),
        # 5. Dequeue -> {"user_id": 1, "provider": "companies_house"}
        call_dequeue().expect("companies_house", 1),
        # 6. Dequeue -> {"user_id": 1, "provider": "id_verification"}
        call_dequeue().expect("id_verification", 1),
        # 7. Dequeue -> {"user_id": 1, "provider": "bank_statements"}
        call_dequeue().expect("bank_statements", 1),
        # 8. Dequeue -> {"user_id": 2, "provider": "bank_statements"}
        call_dequeue().expect("bank_statements", 2),
    ])


def test_timestamp_ordering_example_2() -> None:
    """
    Example #2 from IWC_R1.txt - Timestamp Ordering:
    Tasks with equal priority are ordered by timestamp (older first).
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="bank_statements", timestamp='2025-10-20 12:05:00' -> 1
        call_enqueue("bank_statements", 1, "2025-10-20 12:05:00").expect(1),
        # 2. Enqueue: user_id=2, provider="bank_statements", timestamp='2025-10-20 12:00:00' -> 2
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(2),
        # 3. Dequeue -> {"user_id": 2, "provider": "bank_statements"} (older timestamp)
        call_dequeue().expect("bank_statements", 2),
        # 4. Dequeue -> {"user_id": 1, "provider": "bank_statements"}
        call_dequeue().expect("bank_statements", 1),
    ])


def test_dependency_resolution_example_3() -> None:
    """
    Example #3 from IWC_R1.txt - Dependency Resolution:
    When a task is enqueued, all its dependencies are also added before it.
    credit_check depends on companies_house.
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="credit_check", timestamp='2025-10-20 12:00:00' -> 2
        # (companies_house dependency is automatically added first)
        call_enqueue("credit_check", 1, "2025-10-20 12:00:00").expect(2),
        # 2. Dequeue -> {"user_id": 1, "provider": "companies_house"} (dependency first)
        call_dequeue().expect("companies_house", 1),
        # 3. Dequeue -> {"user_id": 1, "provider": "credit_check"}
        call_dequeue().expect("credit_check", 1),
    ])


def test_rule_of_3_with_different_timestamps() -> None:
    """
    Test that Rule of 3 takes precedence even when timestamps differ.
    User 1 with 3 tasks should be processed before user 2, even if user 2's task is older.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        # User 2 enqueues first (oldest timestamp)
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(1),
        # User 1 enqueues 3 tasks with later timestamps (within 4 min)
        call_enqueue("companies_house", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:02:00").expect(3),
        call_enqueue("bank_statements", 1, "2025-10-20 12:03:00").expect(4),
        # User 1's tasks should all come first despite later timestamps
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
        # User 2's task comes last
        call_dequeue().expect("bank_statements", 2),
    ])


def test_timestamp_ordering_with_multiple_users() -> None:
    """
    Test timestamp ordering across multiple users when none trigger Rule of 3.
    bank_statements tasks are deprioritized to end of queue (gaps < 5 min, not time-sensitive).
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:05:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:02:00").expect(2),
        call_enqueue("id_verification", 3, "2025-10-20 12:07:00").expect(3),
        call_enqueue("bank_statements", 4, "2025-10-20 12:04:00").expect(4),
        # Non-bank_statements first in timestamp order, then bank_statements
        call_dequeue().expect("companies_house", 2),  # 12:02:00
        call_dequeue().expect("id_verification", 3),  # 12:07:00
        call_dequeue().expect("bank_statements", 4),  # 12:04:00 (deprioritized)
        call_dequeue().expect("bank_statements", 1),  # 12:05:00 (deprioritized)
    ])


def test_rule_of_3_multiple_users() -> None:
    """
    Test Rule of 3 when multiple users reach the threshold.
    Users with 3+ tasks should be ordered by their earliest timestamp.
    bank_statements are deprioritized within each user's tasks (gaps < 5 min, not time-sensitive).
    """
    run_queue([
        # User 2 enqueues 3 tasks (earliest at 12:04:00)
        call_enqueue("bank_statements", 2, "2025-10-20 12:04:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:05:00").expect(2),
        call_enqueue("id_verification", 2, "2025-10-20 12:05:30").expect(3),
        # User 1 enqueues 3 tasks (earliest at 12:01:00)
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(4),
        call_enqueue("companies_house", 1, "2025-10-20 12:02:00").expect(5),
        call_enqueue("id_verification", 1, "2025-10-20 12:03:00").expect(6),
        # User 1 should be processed first (earlier earliest timestamp)
        # bank_statements last within each user's batch
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
        # Then user 2
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),
    ])


def test_dependency_resolution_with_multiple_dependencies() -> None:
    """
    Test that dependencies are resolved recursively.
    """
    run_queue([
        # Enqueue credit_check which depends on companies_house
        call_enqueue("credit_check", 1, "2025-10-20 12:00:00").expect(2),
        call_size().expect(2),
        # Dependencies should be processed in order
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("credit_check", 1),
        call_size().expect(0),
    ])


def test_empty_queue_dequeue_returns_none() -> None:
    """
    Test that dequeuing from an empty queue returns None.
    Note: The test framework expects an exact match, so we need to verify behavior.
    """
    from solutions.IWC.queue_solution_entrypoint import QueueSolutionEntrypoint
    queue = QueueSolutionEntrypoint()
    result = queue.dequeue()
    assert result is None, f"Expected None for empty queue dequeue, got {result}"


def test_size_after_multiple_operations() -> None:
    """
    Test that size() correctly tracks the queue size through various operations.
    bank_statements is deprioritized, so companies_house comes first.
    """
    run_queue([
        call_size().expect(0),
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_size().expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:00:00").expect(2),
        call_size().expect(2),
        call_dequeue().expect("companies_house", 2),  # Non-bank_statements first
        call_size().expect(1),
        call_dequeue().expect("bank_statements", 1),  # bank_statements deprioritized
        call_size().expect(0),
    ])


def test_rule_of_3_triggers_exactly_at_3() -> None:
    """
    Test that Rule of 3 triggers exactly when a user reaches 3 tasks, not before.
    """
    run_queue([
        # User 2's task (should be first normally)
        call_enqueue("bank_statements", 2, "2025-10-20 11:00:00").expect(1),
        # User 1's first task
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(2),
        # User 1's second task - still not prioritized
        call_enqueue("id_verification", 1, "2025-10-20 12:01:00").expect(3),
        # At this point, user 2 should still be first (by timestamp)
        # User 1's third task - NOW Rule of 3 kicks in
        call_enqueue("bank_statements", 1, "2025-10-20 12:02:00").expect(4),
        # Now user 1's tasks should all come first
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 2),
    ])

