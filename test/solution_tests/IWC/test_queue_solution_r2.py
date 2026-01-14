from __future__ import annotations

from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def test_deduplication_example_from_spec() -> None:
    """
    Example from IWC_R2.txt - Task Deduplication:
    The second enqueue of "bank_statements" is treated as a duplicate.
    Only one instance remains, keeping the one with older timestamp.
    bank_statements is deprioritized (R3 feature, gaps < 5 min, not time-sensitive).
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="bank_statements", timestamp='2025-10-20 12:00:00' -> 1
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # 2. Enqueue: user_id=1, provider="bank_statements", timestamp='2025-10-20 12:01:00' -> 1 (duplicate)
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(1),
        # 3. Enqueue: user_id=1, provider="id_verification", timestamp='2025-10-20 12:02:00' -> 2
        call_enqueue("id_verification", 1, "2025-10-20 12:02:00").expect(2),
        # 4. Dequeue -> {"user_id": 1, "provider": "id_verification"} (bank_statements deprioritized)
        call_dequeue().expect("id_verification", 1),
        # 5. Dequeue -> {"user_id": 1, "provider": "bank_statements"} (with older timestamp)
        call_dequeue().expect("bank_statements", 1),
    ])


def test_deduplication_keeps_older_timestamp() -> None:
    """
    When a duplicate task is enqueued, the task with the older timestamp is kept.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:10:00").expect(1),
        # Enqueue same task with older timestamp - should replace the existing one
        call_enqueue("companies_house", 1, "2025-10-20 12:05:00").expect(1),
        call_dequeue().expect("companies_house", 1),
    ])


def test_deduplication_newer_timestamp_ignored() -> None:
    """
    When a duplicate task with a newer timestamp is enqueued, it should be ignored.
    """
    run_queue([
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(1),
        # Enqueue same task with newer timestamp - should not replace
        call_enqueue("bank_statements", 2, "2025-10-20 12:10:00").expect(1),
        call_dequeue().expect("bank_statements", 2),
    ])


def test_deduplication_different_users_same_provider() -> None:
    """
    Different users can have the same provider - these are not duplicates.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(2),
        call_enqueue("bank_statements", 3, "2025-10-20 12:00:00").expect(3),
        call_size().expect(3),
    ])


def test_deduplication_same_user_different_providers() -> None:
    """
    Same user can have different providers - these are not duplicates.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(3),
        call_size().expect(3),
    ])


def test_deduplication_with_rule_of_3() -> None:
    """
    Deduplication works correctly with Rule of 3.
    User 1 should reach 3 unique tasks and trigger priority.
    """
    run_queue([
        # User 2's task
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(1),
        # User 1's tasks
        call_enqueue("companies_house", 1, "2025-10-20 12:02:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:01:00").expect(3),
        # Duplicate - doesn't count toward Rule of 3
        call_enqueue("companies_house", 1, "2025-10-20 12:02:00").expect(3),
        # This is the 3rd unique task - should trigger Rule of 3
        call_enqueue("bank_statements", 1, "2025-10-20 12:03:00").expect(4),
        # User 1's tasks should be prioritized
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 2),
    ])


def test_deduplication_with_dependencies() -> None:
    """
    Deduplication works with dependency resolution.
    If credit_check is enqueued twice, dependencies should not be duplicated.
    """
    run_queue([
        # First enqueue of credit_check adds companies_house dependency + credit_check
        call_enqueue("credit_check", 1, "2025-10-20 12:00:00").expect(2),
        # Second enqueue should be deduplicated (both the dependency and the task)
        call_enqueue("credit_check", 1, "2025-10-20 12:05:00").expect(2),
        call_size().expect(2),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("credit_check", 1),
    ])


def test_deduplication_dependency_already_exists() -> None:
    """
    If a dependency task already exists in the queue, it should not be duplicated
    when a dependent task is enqueued.
    """
    run_queue([
        # Enqueue companies_house directly
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        # Enqueue credit_check which depends on companies_house
        # Should only add credit_check, not duplicate companies_house
        call_enqueue("credit_check", 1, "2025-10-20 12:05:00").expect(2),
        call_size().expect(2),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("credit_check", 1),
    ])


def test_deduplication_dependency_with_older_timestamp() -> None:
    """
    If a dependency has an older timestamp than existing task, it should update.
    """
    run_queue([
        # Enqueue companies_house with newer timestamp
        call_enqueue("companies_house", 1, "2025-10-20 12:10:00").expect(1),
        # Enqueue credit_check with older timestamp - dependency should update companies_house
        call_enqueue("credit_check", 1, "2025-10-20 12:00:00").expect(2),
        call_size().expect(2),
    ])


def test_deduplication_after_dequeue_allows_reenqueue() -> None:
    """
    After a task is dequeued, the same (user_id, provider) pair can be enqueued again.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_dequeue().expect("bank_statements", 1),
        call_size().expect(0),
        # Now we can enqueue the same task again
        call_enqueue("bank_statements", 1, "2025-10-20 12:05:00").expect(1),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_deduplication_complex_scenario() -> None:
    """
    Complex scenario combining deduplication with all rules.
    bank_statements deprioritized within user's tasks (R3 feature, gaps < 5 min, not time-sensitive).
    """
    run_queue([
        # User 1 tasks
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 12:01:00").expect(2),
        # User 2 tasks
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(3),
        # User 1 duplicate with newer timestamp (ignored)
        call_enqueue("bank_statements", 1, "2025-10-20 12:02:00").expect(3),
        # User 1 third unique task - triggers Rule of 3
        call_enqueue("id_verification", 1, "2025-10-20 12:03:00").expect(4),
        # User 2 duplicate - ignored
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(4),
        # User 1 should be prioritized (has 3 tasks), bank_statements last
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),  # deprioritized
        # Then user 2
        call_dequeue().expect("bank_statements", 2),  # 11:00:00
    ])


def test_deduplication_multiple_duplicates_keeps_oldest() -> None:
    """
    If the same task is enqueued multiple times, only the oldest timestamp is kept.
    """
    run_queue([
        call_enqueue("id_verification", 5, "2025-10-20 12:05:00").expect(1),
        call_enqueue("id_verification", 5, "2025-10-20 12:02:00").expect(1),
        call_enqueue("id_verification", 5, "2025-10-20 12:08:00").expect(1),
        call_enqueue("id_verification", 5, "2025-10-20 12:01:00").expect(1),
        call_enqueue("id_verification", 5, "2025-10-20 12:10:00").expect(1),
        call_size().expect(1),
        call_dequeue().expect("id_verification", 5),
    ])

