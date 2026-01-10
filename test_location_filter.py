#!/usr/bin/env python3
"""
Test script for location filter functionality.
Run this to verify the location normalization works correctly.
"""

from location_utils import normalize_location, locations_match

def test_location_normalization():
    """Test various location inputs."""

    print("=" * 60)
    print("Testing Location Normalization")
    print("=" * 60)

    test_cases = [
        "California",
        "CA",
        "San Francisco, CA",
        "San Francisco, California",
        "United States",
        "USA",
        "United Kingdom",
        "UK",
        "London, UK",
        "New York, NY",
        "Toronto, Canada",
        "Berlin, Germany",
        "Sydney, Australia",
    ]

    for location in test_cases:
        result = normalize_location(location)
        print(f"\nInput: {location}")
        print(f"  City: {result['city']}")
        print(f"  State: {result['state']} ({result['state_abbr']})")
        print(f"  Country: {result['country']} ({result['country_code']})")


def test_location_matching():
    """Test location matching logic."""

    print("\n" + "=" * 60)
    print("Testing Location Matching")
    print("=" * 60)

    test_pairs = [
        ("California", "CA"),
        ("San Francisco, CA", "California"),
        ("San Francisco", "San Francisco, CA"),
        ("United States", "USA"),
        ("New York", "NY"),
        ("London, UK", "United Kingdom"),
        ("California", "Texas"),
        ("USA", "Canada"),
        ("San Francisco", "Los Angeles"),
    ]

    for loc1, loc2 in test_pairs:
        match = locations_match(loc1, loc2)
        print(f"\n'{loc1}' vs '{loc2}': {'✅ MATCH' if match else '❌ NO MATCH'}")


if __name__ == "__main__":
    test_location_normalization()
    test_location_matching()
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
