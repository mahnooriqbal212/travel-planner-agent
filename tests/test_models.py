from datetime import date

import pytest

from travel_planner.exceptions import TripValidationError
from travel_planner.models import TripRequest


def make(**overrides):
    data = dict(destination="Paris", start_date=date(2026, 12, 1), end_date=date(2026, 12, 3), budget=1000)
    data.update(overrides)
    return TripRequest(**data)


def test_computed_fields(trip):
    assert trip.num_days == 4
    assert trip.num_nights == 3
    assert trip.budget_per_day == 500
    assert trip.budget_per_person_per_day == 250
    assert trip.currency == "USD"  # normalised to upper case


def test_prompt_contains_key_facts(trip):
    text = trip.to_prompt()
    assert "Istanbul" in text and "4 days" in text and "2,000 USD" in text and "Food, History" in text


def test_single_day_trip_is_valid():
    assert make(end_date=date(2026, 12, 1)).num_days == 1


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"destination": "   "}, "Destination is required"),
        ({"end_date": date(2026, 11, 30)}, "End date cannot be before"),
        ({"end_date": date(2027, 1, 30)}, "at most 21 days"),
        ({"budget": 0}, "Budget must be greater than 0"),
        ({"travelers": 0}, "travelers must be between"),
        ({"currency": "DOLLARS"}, "3-letter code"),
        ({"travel_style": "Backpacker"}, "Travel style must be"),
        ({"interests": ["x"] * 11}, "at most 10 interests"),
        ({"notes": "a" * 501}, "500 characters"),
    ],
)
def test_validation_errors(overrides, expected):
    with pytest.raises(TripValidationError) as exc:
        make(**overrides)
    assert any(expected in e for e in exc.value.errors)


def test_all_errors_reported_together():
    with pytest.raises(TripValidationError) as exc:
        make(destination="", budget=-5, currency="1")
    assert len(exc.value.errors) == 3


def test_blank_interests_are_dropped():
    assert make(interests=[" Food ", "", "  "]).interests == ["Food"]
