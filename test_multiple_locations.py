#!/usr/bin/env python3
"""
Test script for multiple location filtering.
Tests that the location filter correctly handles multiple locations.
"""

from location_utils import filter_candidates_by_location


def test_multiple_locations():
    """Test filtering with multiple locations."""

    print("=" * 70)
    print("Testing Multiple Location Filtering")
    print("=" * 70)

    # Sample candidates with different locations
    sample_candidates = [
        {"id": "1", "name": "Alice CA", "location": "San Francisco, CA"},
        {"id": "2", "name": "Bob NY", "location": "New York, NY"},
        {"id": "3", "name": "Carol TX", "location": "Austin, Texas"},
        {"id": "4", "name": "David UK", "location": "London, UK"},
        {"id": "5", "name": "Eve CA", "location": "Los Angeles, California"},
        {"id": "6", "name": "Frank WA", "location": "Seattle, Washington"},
        {"id": "7", "name": "Grace FL", "location": "Miami, FL"},
    ]

    print(f"\nTotal candidates: {len(sample_candidates)}")
    for c in sample_candidates:
        print(f"  - {c['name']}: {c['location']}")

    # Test 1: Single location (should work as before)
    print("\n" + "=" * 70)
    print("Test 1: Single location - 'California'")
    print("=" * 70)

    filtered = filter_candidates_by_location(sample_candidates, "California")
    print(f"Result: {len(filtered)} candidates")
    for c in filtered:
        print(f"  - {c['name']}: {c['location']}")

    expected = 2  # Alice and Eve
    if len(filtered) == expected:
        print(f"✅ PASS: Found {len(filtered)} candidates in California")
    else:
        print(f"❌ FAIL: Expected {expected} but got {len(filtered)}")

    # Test 2: Multiple locations with newlines
    print("\n" + "=" * 70)
    print("Test 2: Multiple locations - 'California\\nNew York\\nTexas'")
    print("=" * 70)

    filtered = filter_candidates_by_location(sample_candidates, "California\nNew York\nTexas")
    print(f"Result: {len(filtered)} candidates")
    for c in filtered:
        print(f"  - {c['name']}: {c['location']}")

    expected = 4  # Alice, Bob, Carol, Eve
    if len(filtered) == expected:
        print(f"✅ PASS: Found {len(filtered)} candidates in CA/NY/TX")
    else:
        print(f"❌ FAIL: Expected {expected} but got {len(filtered)}")

    # Test 3: Multiple locations with newlines
    print("\n" + "=" * 70)
    print("Test 3: Multiple locations - 'CA\\nNY\\nTX\\nFL'")
    print("=" * 70)

    filtered = filter_candidates_by_location(sample_candidates, "CA\nNY\nTX\nFL")
    print(f"Result: {len(filtered)} candidates")
    for c in filtered:
        print(f"  - {c['name']}: {c['location']}")

    expected = 5  # Alice, Bob, Carol, Eve, Grace
    if len(filtered) == expected:
        print(f"✅ PASS: Found {len(filtered)} candidates in CA/NY/TX/FL")
    else:
        print(f"❌ FAIL: Expected {expected} but got {len(filtered)}")

    # Test 4: Mix of countries and states
    print("\n" + "=" * 70)
    print("Test 4: Mix - 'United States\\nUnited Kingdom'")
    print("=" * 70)

    filtered = filter_candidates_by_location(sample_candidates, "United States\nUnited Kingdom")
    print(f"Result: {len(filtered)} candidates")
    for c in filtered:
        print(f"  - {c['name']}: {c['location']}")

    # Should get all of them (all US states + UK)
    expected = 7
    if len(filtered) == expected:
        print(f"✅ PASS: Found all {len(filtered)} candidates")
    else:
        print(f"❌ FAIL: Expected {expected} but got {len(filtered)}")

    # Test 5: State abbreviations
    print("\n" + "=" * 70)
    print("Test 5: State abbreviations - 'CA\\nWA'")
    print("=" * 70)

    filtered = filter_candidates_by_location(sample_candidates, "CA\nWA")
    print(f"Result: {len(filtered)} candidates")
    for c in filtered:
        print(f"  - {c['name']}: {c['location']}")

    expected = 3  # Alice, Eve (CA), Frank (WA)
    if len(filtered) == expected:
        print(f"✅ PASS: Found {len(filtered)} candidates in CA/WA")
    else:
        print(f"❌ FAIL: Expected {expected} but got {len(filtered)}")

    print("\n" + "=" * 70)
    print("Multiple Location Filter Test Completed!")
    print("=" * 70)


if __name__ == "__main__":
    test_multiple_locations()
