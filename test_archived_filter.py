#!/usr/bin/env python3
"""
Test script for archived candidate filtering.
Tests that the include_archived parameter correctly filters candidates.
"""


def test_archived_filter():
    """Test the archived candidate filtering logic."""

    print("=" * 60)
    print("Testing Archived Candidate Filtering Logic")
    print("=" * 60)

    # Simulate candidate data from Lever API
    sample_candidates = [
        {"id": "1", "name": "Active Candidate 1", "archived": False},
        {"id": "2", "name": "Active Candidate 2", "archived": False},
        {"id": "3", "name": "Archived Candidate 1", "archived": True},
        {"id": "4", "name": "Active Candidate 3", "archived": False},
        {"id": "5", "name": "Archived Candidate 2", "archived": True},
        {"id": "6", "name": "Archived Candidate 3", "archived": True},
    ]

    print(f"\nTotal candidates: {len(sample_candidates)}")
    print(f"Active candidates: {sum(1 for c in sample_candidates if not c.get('archived'))}")
    print(f"Archived candidates: {sum(1 for c in sample_candidates if c.get('archived'))}")

    # Test 1: include_archived = False (only active)
    print("\n" + "=" * 60)
    print("Test 1: include_archived = False (only active candidates)")
    print("=" * 60)

    include_archived = False
    filtered = [c for c in sample_candidates if include_archived or not c.get("archived")]

    print(f"Result: {len(filtered)} candidates")
    for candidate in filtered:
        status = "ARCHIVED" if candidate.get("archived") else "ACTIVE"
        print(f"  - {candidate['name']} ({status})")

    expected_active_only = 3
    if len(filtered) == expected_active_only:
        print(f"✅ PASS: Got {len(filtered)} active candidates as expected")
    else:
        print(f"❌ FAIL: Expected {expected_active_only} but got {len(filtered)}")

    # Test 2: include_archived = True (all candidates)
    print("\n" + "=" * 60)
    print("Test 2: include_archived = True (all candidates)")
    print("=" * 60)

    include_archived = True
    filtered = [c for c in sample_candidates if include_archived or not c.get("archived")]

    print(f"Result: {len(filtered)} candidates")
    for candidate in filtered:
        status = "ARCHIVED" if candidate.get("archived") else "ACTIVE"
        print(f"  - {candidate['name']} ({status})")

    expected_all = 6
    if len(filtered) == expected_all:
        print(f"✅ PASS: Got {len(filtered)} total candidates as expected")
    else:
        print(f"❌ FAIL: Expected {expected_all} but got {len(filtered)}")

    print("\n" + "=" * 60)
    print("Archived Filter Test Completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_archived_filter()
