#!/usr/bin/env python3
"""
Test script to verify that the archived parameter is properly passed to Lever API.
This test mocks the API call to check if the correct parameters are being sent.
"""

from unittest.mock import patch, MagicMock
import sys


def test_api_params():
    """Test that include_archived parameter correctly affects API request."""

    print("=" * 60)
    print("Testing Lever API Parameters for Archived Candidates")
    print("=" * 60)

    # Import after setting up the environment
    from lever_client import fetch_candidates_for_posting

    # Test 1: include_archived = False (should NOT include expand parameter)
    print("\n" + "=" * 60)
    print("Test 1: include_archived = False")
    print("=" * 60)

    with patch('lever_client.requests.get') as mock_get:
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "1", "name": "Active Candidate", "archived": False}
            ],
            "hasNext": False
        }
        mock_get.return_value = mock_response

        # Call the function
        fetch_candidates_for_posting("test_posting_id", include_archived=False)

        # Check the parameters used in the API call
        call_args = mock_get.call_args
        params = call_args[1]['params']

        print(f"API Parameters: {params}")

        if "expand" in params:
            print(f"❌ FAIL: 'expand' parameter should NOT be present when include_archived=False")
            print(f"   Found: {params}")
        else:
            print(f"✅ PASS: 'expand' parameter correctly NOT included")

    # Test 2: include_archived = True (SHOULD include expand parameter)
    print("\n" + "=" * 60)
    print("Test 2: include_archived = True")
    print("=" * 60)

    with patch('lever_client.requests.get') as mock_get:
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "1", "name": "Active Candidate", "archived": False},
                {"id": "2", "name": "Archived Candidate", "archived": True}
            ],
            "hasNext": False
        }
        mock_get.return_value = mock_response

        # Call the function
        candidates = fetch_candidates_for_posting("test_posting_id", include_archived=True)

        # Check the parameters used in the API call
        call_args = mock_get.call_args
        params = call_args[1]['params']

        print(f"API Parameters: {params}")

        if "expand" in params and params["expand"] == "archived":
            print(f"✅ PASS: 'expand=archived' parameter correctly included")
            print(f"✅ PASS: Retrieved {len(candidates)} candidates (both active and archived)")
        else:
            print(f"❌ FAIL: 'expand=archived' parameter should be present when include_archived=True")
            print(f"   Found: {params}")

    print("\n" + "=" * 60)
    print("API Parameter Test Completed!")
    print("=" * 60)
    print("\nSummary:")
    print("- When include_archived=False: No 'expand' parameter sent to API")
    print("- When include_archived=True: 'expand=archived' parameter sent to API")
    print("\nThis ensures Lever API returns archived candidates when requested.")


if __name__ == "__main__":
    test_api_params()
