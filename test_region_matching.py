#!/usr/bin/env python3
"""
Test script for region-based location matching.
Tests that regions like "Bay Area" match constituent cities.
"""

from location_utils import locations_match


def test_region_matching():
    """Test that region filters match cities within those regions."""

    print("=" * 70)
    print("Testing Region-Based Location Matching")
    print("=" * 70)

    # Test 1: Bay Area matching
    print("\n" + "=" * 70)
    print("Test 1: 'San Francisco Bay Area' matches Bay Area cities")
    print("=" * 70)

    bay_area_cities = [
        ("San Francisco, CA", True),
        ("Oakland, CA", True),
        ("San Jose, CA", True),
        ("Berkeley, CA", True),
        ("Palo Alto, CA", True),
        ("Los Angeles, CA", False),  # Not in Bay Area
        ("Seattle, WA", False),  # Different region
    ]

    filter_loc = "San Francisco Bay Area"
    passed = 0
    failed = 0

    for candidate_loc, should_match in bay_area_cities:
        result = locations_match(filter_loc, candidate_loc)
        status = "✅ PASS" if result == should_match else "❌ FAIL"
        expected = "should match" if should_match else "should NOT match"
        print(f"{status}: '{candidate_loc}' {expected} - got {result}")
        if result == should_match:
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")

    # Test 2: NYC Metro matching (includes NJ)
    print("\n" + "=" * 70)
    print("Test 2: 'NYC Metro' matches New York and New Jersey cities")
    print("=" * 70)

    nyc_metro_cities = [
        ("New York, NY", True),
        ("Brooklyn, NY", True),
        ("Newark, NJ", True),  # New Jersey
        ("Jersey City, NJ", True),  # New Jersey
        ("Hoboken, NJ", True),  # New Jersey
        ("Philadelphia, PA", False),  # Different metro
        ("Boston, MA", False),  # Different metro
    ]

    filter_loc = "NYC Metro"
    passed = 0
    failed = 0

    for candidate_loc, should_match in nyc_metro_cities:
        result = locations_match(filter_loc, candidate_loc)
        status = "✅ PASS" if result == should_match else "❌ FAIL"
        expected = "should match" if should_match else "should NOT match"
        print(f"{status}: '{candidate_loc}' {expected} - got {result}")
        if result == should_match:
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")

    # Test 3: Silicon Valley matching
    print("\n" + "=" * 70)
    print("Test 3: 'Silicon Valley' matches tech hub cities")
    print("=" * 70)

    silicon_valley_cities = [
        ("Palo Alto, CA", True),
        ("Mountain View, CA", True),
        ("Sunnyvale, CA", True),
        ("Cupertino, CA", True),
        ("San Francisco, CA", False),  # Bay Area but not Silicon Valley proper
        ("Los Angeles, CA", False),
    ]

    filter_loc = "Silicon Valley"
    passed = 0
    failed = 0

    for candidate_loc, should_match in silicon_valley_cities:
        result = locations_match(filter_loc, candidate_loc)
        status = "✅ PASS" if result == should_match else "❌ FAIL"
        expected = "should match" if should_match else "should NOT match"
        print(f"{status}: '{candidate_loc}' {expected} - got {result}")
        if result == should_match:
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")

    print("\n" + "=" * 70)
    print("Region Matching Test Completed!")
    print("=" * 70)


if __name__ == "__main__":
    test_region_matching()
