from __future__ import annotations

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
        call_enqueue("provider_b", 44, iso_ts(delta_minutes=2)).expect(3),
        call_enqueue("provider_c", 44, iso_ts(delta_minutes=2)).expect(3),
        call_size().expect(3),
        call_dequeue().expect("provider_c", 44),
        call_dequeue().expect("provider_b", 44),
        call_dequeue().expect("provider_a", 44),
        call_dequeue().expect("provider_b", 43),
        call_dequeue().expect("provider_a", 42),
    ])
