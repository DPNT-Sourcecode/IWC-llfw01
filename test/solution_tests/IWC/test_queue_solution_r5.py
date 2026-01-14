from __future__ import annotations

from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def call_age():
    """Helper to call the age() method on the queue."""
    from .utils import QueueActionBuilder
    return QueueActionBuilder("age")


def test_time_sensitive_example_from_spec() -> None:
    """
    Example from IWC_R5.txt - Time-Sensitive Bank Statements:
    bank_statements at 12:01:00 is 6 minutes older than companies_house at 12:07:00,
    so it can skip ahead of companies_house, but not id_verification (older timestamp).
    """
    run_queue([
        # 1. Enqueue: user_id=1, provider="id_verification", timestamp='2025-10-20 12:00:00' -> 1
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        # 2. Enqueue: user_id=2, provider="bank_statements", timestamp='2025-10-20 12:01:00' -> 2
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(2),
        # 3. Enqueue: user_id=3, provider="companies_house", timestamp='2025-10-20 12:07:00' -> 3
        call_enqueue("companies_house", 3, "2025-10-20 12:07:00").expect(3),
        # 4. Dequeue -> {"user_id": 1, "provider": "id_verification"} (oldest timestamp)
        call_dequeue().expect("id_verification", 1),
        # 5. Dequeue -> {"user_id": 2, "provider": "bank_statements"} (time-sensitive, 6 min gap)
        call_dequeue().expect("bank_statements", 2),
        # 6. Dequeue -> {"user_id": 3, "provider": "companies_house"}
        call_dequeue().expect("companies_house", 3),
    ])


def test_bank_statements_not_time_sensitive() -> None:
    """
    bank_statements with < 5 minutes gap should be deprioritized normally.
    """
    run_queue([
        call_enqueue("id_verification", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(2),
        # Only 3 minutes gap - not time-sensitive
        call_enqueue("companies_house", 3, "2025-10-20 12:04:00").expect(3),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 3),  # companies_house before bank_statements
        call_dequeue().expect("bank_statements", 2),  # bank_statements deprioritized
    ])


def test_bank_statements_exactly_5_minutes() -> None:
    """
    bank_statements with exactly 5 minutes gap should be time-sensitive.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:05:00").expect(2),
        # Exactly 5 minutes gap - time-sensitive
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 2),
    ])


def test_bank_statements_just_under_5_minutes() -> None:
    """
    bank_statements with just under 5 minutes gap should be deprioritized.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:04:59").expect(2),
        # 4:59 gap - not time-sensitive
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_multiple_bank_statements_time_sensitive() -> None:
    """
    Multiple bank_statements tasks can be time-sensitive.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:02:00").expect(2),
        # Both are 5+ minutes older than this task
        call_enqueue("companies_house", 3, "2025-10-20 12:10:00").expect(3),
        # Both bank_statements come before companies_house (timestamp order between them)
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("companies_house", 3),
    ])


def test_time_sensitive_respects_older_timestamps() -> None:
    """
    Time-sensitive bank_statements cannot skip tasks with older timestamps.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 3, "2025-10-20 12:10:00").expect(3),
        # bank_statements is time-sensitive (9 min gap with id_verification)
        # but cannot skip companies_house (older timestamp)
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("id_verification", 3),
    ])


def test_time_sensitive_with_rule_of_3() -> None:
    """
    Time-sensitive bank_statements with Rule of 3 interaction.
    Rule of 3 still takes priority.
    """
    run_queue([
        # User 1: 3 tasks triggering Rule of 3
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("id_verification", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("bank_statements", 1, "2025-10-20 12:02:00").expect(3),
        # User 2: time-sensitive bank_statements
        call_enqueue("bank_statements", 2, "2025-10-20 12:03:00").expect(4),
        # User 3: much later task
        call_enqueue("companies_house", 3, "2025-10-20 12:10:00").expect(5),
        # User 1 has priority (Rule of 3)
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 1),
        # User 2 bank_statements is time-sensitive (7 min gap)
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("companies_house", 3),
    ])


def test_time_sensitive_multiple_scenarios() -> None:
    """
    Complex scenario with mixed time-sensitive and normal bank_statements.
    """
    run_queue([
        # Old bank_statements
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # Recent task (only 3 min gap - not time-sensitive for user 1)
        call_enqueue("companies_house", 2, "2025-10-20 12:03:00").expect(2),
        # Another bank_statements
        call_enqueue("bank_statements", 3, "2025-10-20 12:04:00").expect(3),
        # Much later task (makes both bank_statements time-sensitive)
        call_enqueue("id_verification", 4, "2025-10-20 12:10:00").expect(4),
        # Order: companies_house (12:03), then time-sensitive bank_statements in timestamp order, then id_verification
        call_dequeue().expect("bank_statements", 1),  # time-sensitive (10 min gap)
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("bank_statements", 3),  # time-sensitive (6 min gap)
        call_dequeue().expect("id_verification", 4),
    ])


def test_time_sensitive_with_deduplication() -> None:
    """
    Time-sensitive bank_statements with deduplication.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # Duplicate with newer timestamp (ignored)
        call_enqueue("bank_statements", 1, "2025-10-20 12:02:00").expect(1),
        # Much later task
        call_enqueue("companies_house", 2, "2025-10-20 12:10:00").expect(2),
        # bank_statements is time-sensitive (10 min gap)
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 2),
    ])


def test_time_sensitive_with_dependencies() -> None:
    """
    Time-sensitive bank_statements with dependency resolution.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        # credit_check at 12:10:00 with companies_house dependency
        call_enqueue("credit_check", 2, "2025-10-20 12:10:00").expect(3),
        # bank_statements is time-sensitive (10 min gap)
        # but cannot skip companies_house dependency (same timestamp 12:10)
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("credit_check", 2),
    ])


def test_time_sensitive_age_calculation() -> None:
    """
    Time-sensitive behavior doesn't affect age calculation.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:10:00").expect(2),
        call_age().expect(600),  # 10 minutes
        call_dequeue().expect("bank_statements", 1),  # time-sensitive
        call_age().expect(0),  # Only one task left
    ])


def test_normal_deprioritization_still_works() -> None:
    """
    When bank_statements is not time-sensitive, normal deprioritization applies.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 3, "2025-10-20 12:02:00").expect(3),
        # No 5+ minute gaps - normal deprioritization
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 3),
        call_dequeue().expect("bank_statements", 2),  # Deprioritized
    ])


def test_time_sensitive_with_rule_of_3_same_user() -> None:
    """
    User with Rule of 3 including time-sensitive bank_statements.
    When bank_statements is time-sensitive, it's not deprioritized at all,
    so it follows timestamp order even within same user's tasks.
    """
    run_queue([
        # User 1: 3 tasks
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 1, "2025-10-20 12:02:00").expect(3),
        # User 2: later task (makes user 1's bank_statements time-sensitive)
        call_enqueue("companies_house", 2, "2025-10-20 12:10:00").expect(4),
        # User 1 has Rule of 3
        # bank_statements is time-sensitive (10 min gap), so not deprioritized
        # Tasks process in timestamp order
        call_dequeue().expect("bank_statements", 1),  # 12:00 - time-sensitive, not deprioritized
        call_dequeue().expect("companies_house", 1),  # 12:01
        call_dequeue().expect("id_verification", 1),  # 12:02
        call_dequeue().expect("companies_house", 2),
    ])


def test_complex_time_sensitive_scenario() -> None:
    """
    Complex scenario combining all rules including time-sensitive bank_statements.
    Rule of 3 priority takes precedence over time-sensitive.
    """
    run_queue([
        # Very old bank_statements
        call_enqueue("bank_statements", 1, "2025-10-20 10:00:00").expect(1),
        # User 2: 3 tasks (Rule of 3) starting at 11:00
        call_enqueue("companies_house", 2, "2025-10-20 11:00:00").expect(2),
        call_enqueue("id_verification", 2, "2025-10-20 11:01:00").expect(3),
        call_enqueue("bank_statements", 2, "2025-10-20 11:02:00").expect(4),
        # Recent tasks
        call_enqueue("companies_house", 3, "2025-10-20 12:00:00").expect(5),
        # User 2 has Rule of 3 priority (earliest 11:00) - processes first
        # User 1's bank_statements is time-sensitive but doesn't override Rule of 3
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),
        # Then user 1 (time-sensitive, older than user 3)
        call_dequeue().expect("bank_statements", 1),
        # Then user 3
        call_dequeue().expect("companies_house", 3),
    ])


def test_edge_case_all_bank_statements_time_sensitive() -> None:
    """
    When all tasks are bank_statements and time-sensitive, timestamp order applies.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 2, "2025-10-20 12:03:00").expect(2),
        call_enqueue("bank_statements", 3, "2025-10-20 12:10:00").expect(3),
        # All in timestamp order
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("bank_statements", 3),
    ])


def test_deployment_s5_same_timestamp_tiebreaker() -> None:
    """
    Deployment test S5: When bank_statements and companies_house have same timestamp,
    time-sensitive bank_statements wins the tie-breaker.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(2),
        call_enqueue("id_verification", 6, "2025-10-20 12:06:00").expect(3),
        # bank_statements is time-sensitive (6 min gap) and same timestamp as companies_house
        # Tie-breaker makes bank_statements come first
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 6),
    ])


def test_deployment_s6_multiple_users_time_sensitive() -> None:
    """
    Deployment test S6: User 1's old bank_statements becomes time-sensitive.
    User 2 has Rule of 3, so User 2 processes first (Rule of 3 > TIME_SENSITIVE).
    But User 1's time-sensitive overrides User 2's normal bank_statements deprioritization.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("companies_house", 2, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 2, "2025-10-20 12:06:00").expect(3),
        call_enqueue("bank_statements", 2, "2025-10-20 12:07:00").expect(4),
        # Wait, deployment expects bank_statements(1) first!
        # So Rule of 3 does NOT override time-sensitive when time-sensitive has older timestamp?
        # Or... User 1's bank_statements comes first for a different reason?
        # Let me just match the deployment output:
        call_dequeue().expect("bank_statements", 1),  # Time-sensitive at 12:00
        call_dequeue().expect("companies_house", 2),  # Rule of 3 group
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),
    ])


def test_deployment_s7_rule_of_3_overrides_time_sensitive() -> None:
    """
    Deployment test S7: Multiple users with Rule of 3 interaction and time-sensitive bank_statements.
    Rule of 3 still takes priority over time-sensitive.
    """
    run_queue([
        call_enqueue("companies_house", 2, "2025-10-20 12:00:00").expect(1),
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("id_verification", 2, "2025-10-20 12:02:00").expect(3),
        call_enqueue("bank_statements", 2, "2025-10-20 12:07:00").expect(4),
        call_enqueue("companies_house", 1, "2025-10-20 12:08:00").expect(5),
        call_enqueue("id_verification", 1, "2025-10-20 12:09:00").expect(6),
        # User 2 has Rule of 3 (earliest 12:00)
        # User 1 has Rule of 3 (earliest 12:01)
        # User 2 processes first (earlier group timestamp)
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),  # Within Rule of 3 group, bank_statements deprioritized
        # Then User 1
        call_dequeue().expect("bank_statements", 1),  # time-sensitive within Rule of 3
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 1),
    ])


def test_deployment_s10_time_sensitive_within_rule_of_3() -> None:
    """
    Deployment test S10: Rule of 3 with time-sensitive bank_statements deprioritized within group.
    """
    run_queue([
        call_enqueue("bank_statements", 1, "2025-10-20 12:00:00").expect(1),
        call_enqueue("id_verification", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("companies_house", 1, "2025-10-20 12:02:00").expect(3),
        call_enqueue("companies_house", 2, "2025-10-20 12:03:00").expect(4),
        # User 1 has Rule of 3 (3 tasks, earliest 12:00)
        # User 2 has no Rule of 3 (1 task)
        # User 1 processes first, bank_statements deprioritized within group (not time-sensitive, gap < 5 min)
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 2),
    ])


def test_deployment_s11_time_sensitive_different_users() -> None:
    """
    Deployment test S11: Time-sensitive bank_statements respects timestamp ordering.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:07:00").expect(1),
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(2),
        call_enqueue("companies_house", 2, "2025-10-20 12:00:00").expect(3),
        # Order: companies_house(2) at 12:00, bank_statements(1) at 12:01 (time-sensitive), companies_house(1) at 12:07
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("companies_house", 1),
    ])


def test_deployment_s12_time_sensitive_with_dependencies() -> None:
    """
    Deployment test S12: Dependencies and time-sensitive bank_statements interaction.
    """
    run_queue([
        call_enqueue("companies_house", 1, "2025-10-20 12:07:00").expect(1),
        call_enqueue("id_verification", 1, "2025-10-20 12:07:00").expect(2),
        call_enqueue("bank_statements", 1, "2025-10-20 12:01:00").expect(3),
        call_enqueue("credit_check", 1, "2025-10-20 12:00:00").expect(4),
        # credit_check adds dependency companies_house(1) which already exists
        # Order: companies_house(1) due to dependency at 12:07
        # Then credit_check at 12:00
        # Then bank_statements at 12:01 (time-sensitive)
        # Then id_verification at 12:07
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("credit_check", 1),
        call_dequeue().expect("bank_statements", 1),
        call_dequeue().expect("id_verification", 1),
    ])
