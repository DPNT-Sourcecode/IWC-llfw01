from __future__ import annotations

from datetime import datetime, timezone
from .utils import call_dequeue, call_enqueue, call_size, iso_ts, run_queue


def test_enqueue_size_dequeue_flow() -> None:
    run_queue([
        call_enqueue("companies_house", 1, iso_ts(delta_minutes=0)).expect(1),
        call_size().expect(1),
        call_dequeue().expect("companies_house", 1),
    ])

def test_rule_of_3() -> None: 
    run_queue([
        call_enqueue("provider_a", 42, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("provider_b", 43, iso_ts(delta_minutes=1)).expect(2),
        call_enqueue("provider_a", 44, iso_ts(delta_minutes=2)).expect(3),
        call_enqueue("provider_b", 44, iso_ts(delta_minutes=2)).expect(4),
        call_enqueue("provider_c", 44, iso_ts(delta_minutes=2)).expect(1),
        call_size().expect(3),
        call_dequeue().expect("provider_c", 44),
        call_dequeue().expect("provider_b", 44),
        call_dequeue().expect("provider_a", 44),
        call_dequeue().expect("provider_b", 43),
        call_dequeue().expect("provider_a", 42),
    ])


def test_timestamp_ordering() -> None:
    run_queue([
        call_enqueue("provider_x", 7, iso_ts(delta_minutes=5)).expect(1),
        call_enqueue("provider_y", 8, iso_ts(delta_minutes=3)).expect(2),
        call_enqueue("provider_z", 9, iso_ts(delta_minutes=4)).expect(3),
        call_size().expect(3),
        call_dequeue().expect("provider_y", 8),
        call_dequeue().expect("provider_z", 9),
        call_dequeue().expect("provider_x", 7),
    ])


def test_dependencys() -> None:
    run_queue([
        call_enqueue(
            "provider_dep", 10, iso_ts(delta_minutes=0)
        ).expect(3),
        call_size().expect(3),
        call_dequeue().expect("provider_a", 1),
        call_dequeue().expect("provider_b", 2),
        call_dequeue().expect("provider_dep", 10),
    ])


def test_deduplication() -> None:
    run_queue([
        call_enqueue("provider_dup", 5, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("provider_dup", 5, iso_ts(delta_minutes=1)).expect(1),
        call_size().expect(1),
        call_dequeue().expect("provider_dup", 5),
    ])

def test_deprioritize_bank_statements() -> None:
    run_queue([
        call_enqueue("bank_statements", 1, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("id_verification", 1, iso_ts(delta_minutes=1)).expect(2),
        call_enqueue("companies_house", 2, iso_ts(delta_minutes=2)).expect(3),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 2),
        call_dequeue().expect("bank_statements", 1),
    ])


def test_deprioritize_bank_statements_with_rule_of_3() -> None:
    """Test IWC_R3_S4: User with 3 tasks (Rule of 3) should have bank_statements after other tasks but before other users"""
    run_queue([
        call_enqueue("bank_statements", 1, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("id_verification", 1, iso_ts(delta_minutes=0)).expect(2),
        call_enqueue("companies_house", 1, iso_ts(delta_minutes=0)).expect(3),
        call_enqueue("companies_house", 2, iso_ts(delta_minutes=0)).expect(4),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("bank_statements", 1),  # User 1's bank_statements before user 2
        call_dequeue().expect("companies_house", 2),
    ])


def test_deprioritize_bank_statements_with_rule_of_3_different_timestamps() -> None:
    """Test IWC_R3_S5: User with 3 tasks (Rule of 3) with different timestamps"""
    run_queue([
        call_enqueue("bank_statements", 1, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("id_verification", 1, iso_ts(delta_minutes=1)).expect(2),
        call_enqueue("companies_house", 1, iso_ts(delta_minutes=2)).expect(3),
        call_enqueue("companies_house", 2, iso_ts(delta_minutes=3)).expect(4),
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("bank_statements", 1),  # User 1's bank_statements before user 2
        call_dequeue().expect("companies_house", 2),
    ])


def test_queue_age() -> None:
    """Test IWC_R4: Queue internal age based on task timestamps"""
    from .utils import QueueActionBuilder
    
    def call_age() -> QueueActionBuilder:
        return QueueActionBuilder("age")
    
    run_queue([
        # Empty queue should have age 0
        call_age().expect(0),
        # Add first task at T+0
        call_enqueue("id_verification", 1, iso_ts(delta_minutes=0)).expect(1),
        call_age().expect(0),  # Only one task, age is 0
        # Add second task at T+5 minutes
        call_enqueue("id_verification", 2, iso_ts(delta_minutes=5)).expect(2),
        call_age().expect(300),  # 5 minutes = 300 seconds
        # Add third task at T+10 minutes
        call_enqueue("companies_house", 3, iso_ts(delta_minutes=10)).expect(3),
        call_age().expect(600),  # 10 minutes = 600 seconds (oldest to newest)
        # Dequeue oldest task
        call_dequeue().expect("id_verification", 1),
        call_age().expect(300),  # Now gap is from T+5 to T+10 = 5 minutes
        # Dequeue another
        call_dequeue().expect("id_verification", 2),
        call_age().expect(0),  # Only one task left
        # Dequeue last
        call_dequeue().expect("companies_house", 3),
        call_age().expect(0),  # Empty queue
    ])

def test_time_sensitive_bank_statements() -> None:
    """Test IWC_R5: Bank statements with 5+ minute internal age get elevated"""
    run_queue([
        call_enqueue("id_verification", 1, iso_ts(delta_minutes=0)).expect(1),
        call_enqueue("bank_statements", 2, iso_ts(delta_minutes=1)).expect(2),
        call_enqueue("companies_house", 3, iso_ts(delta_minutes=7)).expect(3),
        # bank_statements is 6 minutes older than companies_house, so it gets elevated
        call_dequeue().expect("id_verification", 1),  # Oldest timestamp
        call_dequeue().expect("bank_statements", 2),  # Old enough, elevated
        call_dequeue().expect("companies_house", 3),  # Newest timestamp
    ])


def test_iwc_r5_s5() -> None:
    """IWC_R5_S5: Bank statements with same timestamp as other task - elevated comes first"""
    run_queue([
        call_enqueue("companies_house", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(1),
        call_enqueue("bank_statements", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(2),
        call_enqueue("id_verification", 6, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=6)).expect(3),
        call_dequeue().expect("bank_statements", 1),  # Elevated (6 min age), comes first despite same timestamp
        call_dequeue().expect("companies_house", 1),
        call_dequeue().expect("id_verification", 6),
    ])


def test_iwc_r5_s6() -> None:
    """IWC_R5_S6: Multiple users with bank_statements - elevated comes before Rule of 3"""
    run_queue([
        call_enqueue("bank_statements", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(1),
        call_enqueue("companies_house", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=1)).expect(2),
        call_enqueue("id_verification", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=6)).expect(3),
        call_enqueue("bank_statements", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=7)).expect(4),
        call_dequeue().expect("bank_statements", 1),  # Elevated (7 min age) - comes before Rule of 3
        call_dequeue().expect("companies_house", 2),  # User 2 has Rule of 3
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 2),  # User 2's bank_statements (part of Rule of 3)
    ])


def test_iwc_r5_s7() -> None:
    """IWC_R5_S7: Complex scenario with Rule of 3 and elevated bank_statements"""
    run_queue([
        call_enqueue("companies_house", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(1),
        call_enqueue("bank_statements", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=1)).expect(2),
        call_enqueue("id_verification", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=2)).expect(3),
        call_enqueue("bank_statements", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=7)).expect(4),
        call_enqueue("companies_house", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=8)).expect(5),
        call_enqueue("id_verification", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=9)).expect(6),
        call_dequeue().expect("companies_house", 2),  # User 2 Rule of 3
        call_dequeue().expect("id_verification", 2),
        call_dequeue().expect("bank_statements", 1),  # User 1 bank_statements elevated (8 min old from newest)
        call_dequeue().expect("companies_house", 1),  # User 1 Rule of 3
        call_dequeue().expect("id_verification", 1),
        call_dequeue().expect("bank_statements", 2),  # User 2 bank_statements (not old enough)
    ])


def test_iwc_r5_s8() -> None:
    """IWC_R5_S8: Multiple bank_statements tasks that are old enough"""
    run_queue([
        call_enqueue("bank_statements", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(1),
        call_enqueue("bank_statements", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(2),
        call_enqueue("companies_house", 3, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=1)).expect(3),
        call_enqueue("id_verification", 3, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=7)).expect(4),
        call_dequeue().expect("bank_statements", 1),  # Both elevated, timestamp order
        call_dequeue().expect("bank_statements", 2),
        call_dequeue().expect("companies_house", 3),
        call_dequeue().expect("id_verification", 3),
    ])


def test_iwc_r5_s11() -> None:
    """IWC_R5_S11: Elevated bank_statements respects older timestamps"""
    run_queue([
        call_enqueue("companies_house", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=7)).expect(1),
        call_enqueue("bank_statements", 1, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=1)).expect(2),
        call_enqueue("companies_house", 2, iso_ts(base=datetime(2025, 10, 20, 12, 0, tzinfo=timezone.utc), delta_minutes=0)).expect(3),
        call_dequeue().expect("companies_house", 2),  # Oldest timestamp
        call_dequeue().expect("bank_statements", 1),  # Elevated, but after older companies_house(2)
        call_dequeue().expect("companies_house", 1),  # Newest
    ])

