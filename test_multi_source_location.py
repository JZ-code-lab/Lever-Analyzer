#!/usr/bin/env python3
"""
Test script for multi-source location detection.
Tests that location can be detected from:
1. Lever location field
2. Resume text
3. Phone number area code
"""

from location_utils import (
    get_candidate_location_multi_source,
    extract_location_from_resume,
    get_location_from_phone_number,
    extract_phone_numbers
)


def test_multi_source_location():
    """Test location detection from multiple sources."""

    print("=" * 70)
    print("Testing Multi-Source Location Detection")
    print("=" * 70)

    # Test 1: Lever location field (should use this first)
    print("\n" + "=" * 70)
    print("Test 1: Lever location field (highest priority)")
    print("=" * 70)

    candidate_with_lever_location = {
        "id": "123",
        "name": "Test Candidate 1",
        "location": "San Francisco, CA"
    }

    result = get_candidate_location_multi_source(candidate_with_lever_location)
    print(f"Candidate with Lever location: {result}")
    print(f"✅ PASS" if result == "San Francisco, CA" else f"❌ FAIL")

    # Test 2: Resume text location (when Lever field is empty)
    print("\n" + "=" * 70)
    print("Test 2: Resume text location (fallback when Lever is empty)")
    print("=" * 70)

    candidate_no_lever = {
        "id": "124",
        "name": "Test Candidate 2"
    }

    resume_text = """
    John Doe
    Seattle, WA 98101
    john.doe@email.com
    (206) 555-1234

    EXPERIENCE
    Software Engineer at Microsoft
    Redmond, WA
    2020-2023
    """

    result = get_candidate_location_multi_source(candidate_no_lever, resume_text)
    print(f"Candidate with resume location: {result}")
    print(f"✅ PASS" if result and "Seattle" in result else f"❌ FAIL")

    # Test 3: Phone number area code (when both Lever and resume don't have location)
    print("\n" + "=" * 70)
    print("Test 3: Phone number area code (last resort)")
    print("=" * 70)

    candidate_with_phone = {
        "id": "125",
        "name": "Test Candidate 3",
        "phones": [{"value": "415-555-1234"}]
    }

    result = get_candidate_location_multi_source(candidate_with_phone)
    print(f"Candidate with phone (415): {result}")
    print(f"✅ PASS" if result and "California" in result else f"❌ FAIL (got: {result})")

    # Test 4: Extract location from resume
    print("\n" + "=" * 70)
    print("Test 4: Extract location patterns from resume text")
    print("=" * 70)

    resume_samples = [
        ("New York, NY 10001\nJohn Smith", "New York, NY"),
        ("Location: Austin, TX", "Austin, TX"),
        ("Based in Portland, OR", "Portland, OR"),
        ("1234 Main St, Boston, MA 02101", "Main St, MA"),
    ]

    for resume, expected_contains in resume_samples:
        location = extract_location_from_resume(resume)
        status = "✅ PASS" if location and expected_contains.split(",")[0] in location else "❌ FAIL"
        print(f"{status}: '{resume[:30]}...' -> {location}")

    # Test 5: Extract phone numbers from text
    print("\n" + "=" * 70)
    print("Test 5: Extract phone numbers from text")
    print("=" * 70)

    phone_samples = [
        "Call me at 415-555-1234",
        "Phone: (650) 555-9999",
        "Mobile: 206.555.7777",
        "+1-408-555-3333"
    ]

    for text in phone_samples:
        phones = extract_phone_numbers(text)
        status = "✅ PASS" if phones else "❌ FAIL"
        print(f"{status}: '{text}' -> {phones}")

    # Test 6: Get location from phone number
    print("\n" + "=" * 70)
    print("Test 6: Get location from phone area codes")
    print("=" * 70)

    phone_area_codes = [
        ("415-555-1234", "California"),
        ("206-555-1234", "Washington"),
        ("212-555-1234", "New York"),
        ("512-555-1234", "Texas"),
    ]

    for phone, expected_state in phone_area_codes:
        location = get_location_from_phone_number(phone)
        status = "✅ PASS" if location and expected_state in location else "❌ FAIL"
        print(f"{status}: {phone} -> {location}")

    # Test 7: Priority order (Lever > Resume > Phone)
    print("\n" + "=" * 70)
    print("Test 7: Priority order - Lever should win even when all sources present")
    print("=" * 70)

    candidate_all_sources = {
        "id": "126",
        "name": "Test Candidate 4",
        "location": "Miami, FL",  # Should use this
        "phones": [{"value": "415-555-1234"}]  # Should NOT use this
    }

    resume_with_location = "Seattle, WA\nSoftware Engineer"  # Should NOT use this

    result = get_candidate_location_multi_source(candidate_all_sources, resume_with_location)
    print(f"All sources present, should use Lever: {result}")
    print(f"✅ PASS" if result == "Miami, FL" else f"❌ FAIL (got: {result})")

    print("\n" + "=" * 70)
    print("Multi-Source Location Detection Test Completed!")
    print("=" * 70)


if __name__ == "__main__":
    test_multi_source_location()
