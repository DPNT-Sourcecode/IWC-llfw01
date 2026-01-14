from __future__ import annotations

from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def test_bank_statements_deprioritization_example_from_spec() -> None:
    """
    Example from IWC_R3.txt - Bank Statements Deprioritization:
    Even though bank_statements was enqueued first, it is held back.
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="bank_statements", timestamp='2025-10-20 12:00:00' -> 1
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # 2. Enqueue: user_id=1, provider="id_verification", timestamp='2025-10-20 12:01:00' -> 2
        call_enqueue("id_verification", 1, "2025-10-20 12:01:00").expect(2),
        # 3. Enqueue: user_id=2, provider="companies_house", timestamp='2025-10-20 12:02:00' -> 3
        call_enqueue("companies_house", 2, "2025-10-20 12:02:00").expect(3),
        # 4. Dequeue -> {"user_id": 1, "provider": "id_verification"}
        call_dequeue().expect("id_verification", 1),
        # 5. Dequeue -> {"user_id": 2, "provider": "companies_house"}
        call_dequeue().expect("companies_house", 2),
        # 6. Dequeue -> {"user_id": 1, "provider": "bank_statements"}
        call_dequeue().expect("bank_statements", 1),
    ])


def test_bank_statements_global_deprioritization() -> None:
    """
    Bank statements tasks go to the end of the global queue when user has < 3 tasks.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 3, "2025-10-20 12:02:00").expect(3),
        # Bank statements should be last despite earliest timestamp
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("id_verification", 3),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_bank_statements_deprioritized_within_user_with_rule_of_3() -> None:
    """
    When a user has Rule of 3, their bank_statements task comes after their other tasks.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:02:00").expect(3),
        # User 1 has 3 tasks, Rule of 3 applies
        # But bank_statements should be last among user 1's tasks
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_multiple_bank_statements_all_deprioritized() -> None:
    """
    Multiple bank_statements tasks from different users are all deprioritized.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(2),
        call_enqueue("companies_house", 3, "2025-10-20 12:02:00").expect(3),
        # companies_house should be first despite later timestamp
        call_dequeue().expect("companies_house", 3),
        # Then bank_statements in timestamp order
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 2),
    ])


def test_non_bank_statements_ordered_by_timestamp() -> None:
    """
    Non-bank_statements tasks should still follow normal timestamp ordering.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:05:00").expect(1),
        call_enqueue("id_verification", 2, "2025-10-20 12:02:00").expect(2),
        call_enqueue("companies_house", 3, "2025-10-20 12:08:00").expect(3),
        # Should dequeue in timestamp order
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("companies_house", 3),
    ])


def test_bank_statements_with_rule_of_3_multiple_users() -> None:
    """
    Multiple users with Rule of 3: bank_statements is last within each user's batch.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        # User 1: 3 tasks including bank_statements (earliest at 11:00)
        call_enqueue("bank_statements", 1, "2025-10-20 11:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 11:01:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 11:02:00").expect(3),
        # User 2: 3 tasks including bank_statements (earliest at 11:02:30)
        call_enqueue("companies_house", 2, "2025-10-20 11:02:30").expect(4),
        call_enqueue("id_verification", 2, "2025-10-20 11:03:00").expect(5),
        call_enqueue("bank_statements", 2, "2025-10-20 11:04:00").expect(6),
        # User 1 processes first (earlier earliest timestamp)
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),  # Last of user 1's tasks
        # Then user 2
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),  # Last of user 2's tasks
    ])


def test_bank_statements_only_user() -> None:
    """
    User with only bank_statements task should still be processed.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_size().expect(1),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_mixed_scenario_rule_of_3_and_deprioritization() -> None:
    """
    Complex scenario: User 1 has Rule of 3, User 2 does not.
    """
    run_queue([
        # User 2: only bank_statements (should go to end globally)
        call_enqueue("bank_statements", 2, "2025-10-20 12:00:00").expect(1),
        # User 1: 3 tasks triggering Rule of 3
        call_enqueue("companies_house", 1, "2025-10-20 12:02:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:03:00").expect(3),
        call_enqueue("bank_statements", 1, "2025-10-20 12:04:00").expect(4),
        # User 1 has priority (Rule of 3)
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),  # User 1's bank_statements
        # Then user 2's bank_statements (globally deprioritized)
        call_dequeue().expect("bank_statements", 2),
    ])


def test_bank_statements_deprioritization_with_dependencies() -> None:
    """
    Bank statements deprioritization works with dependency resolution.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # credit_check depends on companies_house
        call_enqueue("credit_check", 2, "2025-10-20 12:02:00").expect(3),
        # companies_house and credit_check should come before bank_statements
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("credit_check", 2),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_bank_statements_with_deduplication() -> None:
    """
    Bank statements deprioritization works with deduplication.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:05:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:00:00").expect(2),
        # Duplicate bank_statements with older timestamp
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(2),
        # companies_house first, then bank_statements (deprioritized)
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_user_with_2_tasks_one_bank_statements() -> None:
    """
    User with 2 tasks (one bank_statements) - Rule of 3 doesn't apply.
    Bank statements goes to end of global queue. Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 2, "2025-10-20 12:02:00").expect(3),
        # User 1 has 2 tasks, no Rule of 3
        # Non-bank_statements tasks first
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 2),
        # Then bank_statements
        call_dequeue().expect("bank_statements", 1),
    ])


def test_all_tasks_are_bank_statements() -> None:
    """
    When all tasks are bank_statements, they should follow timestamp ordering.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:05:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:02:00").expect(2),
        call_enqueue("bank_statements", 3, "2025-10-20 12:08:00").expect(3),
        # All bank_statements, ordered by timestamp
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 3),
    ])


def test_complex_scenario_all_rules() -> None:
    """
    Complex scenario combining all rules: Rule of 3, deduplication, dependencies, and bank_statements deprioritization.
    Gaps < 5 min to avoid time-sensitive behavior.
    """
    run_queue([
        # User 1: Will reach Rule of 3
        call_enqueue("bank_statements", 1, "2025-10-20 11:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 11:01:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 11:02:00").expect(3),
        # User 2: Has 2 tasks, no Rule of 3
        call_enqueue("bank_statements", 2, "2025-10-20 11:03:00").expect(4),
        call_enqueue("companies_house", 2, "2025-10-20 11:04:00").expect(5),
        # User 3: credit_check with dependency
        call_enqueue("credit_check", 3, "2025-10-20 11:04:30").expect(7),
        # User 1 has Rule of 3 priority
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),  # Last of user 1's
        # Then non-bank_statements from users 2 and 3
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("companies_house", 3),  # Dependency
        call_dequeue().expect("credit_check", 3),
        # Finally bank_statements from user 2
        call_dequeue().expect("bank_statements", 2),
    ])

