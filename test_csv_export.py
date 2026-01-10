#!/usr/bin/env python3
"""
Test script for CSV export functionality.
Run this to verify the CSV export with HYPERLINK formulas works correctly.
"""

from export_utils import export_results_to_csv, filter_results_by_score


def test_csv_export():
    """Test CSV export with sample data."""

    print("=" * 60)
    print("Testing CSV Export with HYPERLINK Formulas")
    print("=" * 60)

    # Create sample results data
    sample_results = [
        {
            "candidate": {
                "id": "candidate-123",
                "name": "John Doe",
                "emails": ["john.doe@example.com"],
                "links": ["https://www.linkedin.com/in/johndoe"],
                "_posting_name": "Senior Software Engineer"
            },
            "analysis": {
                "overall_score": 85,
                "summary": "Strong candidate with excellent technical skills.",
                "strengths": ["10+ years Python", "Leadership experience", "Open source contributor"],
                "weaknesses": ["Limited cloud experience", "No Docker knowledge"],
                "jd_match_score": 90,
                "requirement_scores": {
                    "Python experience": 95,
                    "Team leadership": 85,
                    "Cloud platforms": 60
                }
            }
        },
        {
            "candidate": {
                "id": "candidate-456",
                "name": "Jane Smith",
                "emails": ["jane.smith@example.com"],
                "links": ["https://www.linkedin.com/in/janesmith"],
                "_posting_name": "Senior Software Engineer"
            },
            "analysis": {
                "overall_score": 72,
                "summary": "Good candidate with solid fundamentals.",
                "strengths": ["Strong communication", "Fast learner"],
                "weaknesses": ["Junior level experience", "No production experience"],
                "jd_match_score": 70,
                "requirement_scores": {
                    "Python experience": 65,
                    "Team leadership": 60,
                    "Cloud platforms": 80
                }
            }
        },
        {
            "candidate": {
                "id": "candidate-789",
                "name": "Bob Johnson",
                "emails": [],
                "links": [],
                "_posting_name": "Data Scientist"
            },
            "analysis": {
                "overall_score": 45,
                "summary": "Needs more experience.",
                "strengths": ["Enthusiasm"],
                "weaknesses": ["No relevant experience", "Career change"],
                "jd_match_score": 40,
                "requirement_scores": {
                    "Python experience": 30,
                    "Team leadership": 20,
                    "Cloud platforms": 50
                }
            }
        }
    ]

    # Test 1: Export all results
    print("\n✓ Test 1: Export all results")
    csv_data = export_results_to_csv(sample_results)
    print(f"  Generated CSV with {len(csv_data)} characters")

    # Show first few lines
    lines = csv_data.split('\n')
    print(f"\n  Preview (first 5 lines):")
    for i, line in enumerate(lines[:5]):
        print(f"    {i+1}: {line[:100]}{'...' if len(line) > 100 else ''}")

    # Check for HYPERLINK formulas
    if '=HYPERLINK(' in csv_data:
        print("\n  ✅ HYPERLINK formulas found in CSV")
        # Count hyperlinks
        hyperlink_count = csv_data.count('=HYPERLINK(')
        print(f"  Found {hyperlink_count} hyperlinks")
    else:
        print("\n  ❌ WARNING: No HYPERLINK formulas found")

    # Test 2: Filter by minimum score
    print("\n✓ Test 2: Filter by minimum score (70)")
    filtered = filter_results_by_score(sample_results, 70)
    print(f"  Filtered to {len(filtered)} candidates (from {len(sample_results)})")

    filtered_csv = export_results_to_csv(filtered)
    print(f"  Generated filtered CSV with {len(filtered_csv)} characters")

    # Test 3: Filter with high threshold
    print("\n✓ Test 3: Filter by minimum score (90)")
    filtered_high = filter_results_by_score(sample_results, 90)
    print(f"  Filtered to {len(filtered_high)} candidates (from {len(sample_results)})")

    # Test 4: Write to file for manual inspection
    print("\n✓ Test 4: Writing sample CSV to file")
    with open("/home/runner/workspace/sample_export.csv", "w") as f:
        f.write(csv_data)
    print("  Saved to: sample_export.csv")
    print("  You can download this file and open it in Excel or Google Sheets to verify hyperlinks work")

    print("\n" + "=" * 60)
    print("CSV Export Test Completed!")
    print("=" * 60)
    print("\nTo verify hyperlinks work:")
    print("1. Download sample_export.csv")
    print("2. Open in Excel or Google Sheets")
    print("3. Click on cells in 'Lever Profile' or 'LinkedIn Profile' columns")
    print("4. Hyperlinks should be clickable")


if __name__ == "__main__":
    test_csv_export()
