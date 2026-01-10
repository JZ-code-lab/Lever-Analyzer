import re
from typing import Optional
import country_converter as coco
import us


def normalize_location(location: str) -> dict:
    """
    Normalize a location string into standardized components.

    Returns a dict with:
    - city: normalized city name (if found)
    - state: normalized US state name (if found)
    - state_abbr: US state abbreviation (if found)
    - country: normalized country name (if found)
    - country_code: ISO3 country code (if found)
    - original: original input
    """
    if not location:
        return {
            "city": None,
            "state": None,
            "state_abbr": None,
            "country": None,
            "country_code": None,
            "original": ""
        }

    location = location.strip()
    original = location

    result = {
        "city": None,
        "state": None,
        "state_abbr": None,
        "country": None,
        "country_code": None,
        "original": original
    }

    # Split by common delimiters (comma, semicolon, dash, slash)
    parts = re.split(r'[,;/\-]', location)
    parts = [p.strip() for p in parts if p.strip()]

    # Initialize country converter
    cc = coco.CountryConverter()

    # Try to identify each part
    for part in parts:
        # Check if it's a US state (by name or abbreviation)
        state = us.states.lookup(part)
        if state:
            result["state"] = state.name
            result["state_abbr"] = state.abbr
            result["country"] = "United States"
            result["country_code"] = "USA"
            continue

        # Check if it's a country
        try:
            country_name = cc.convert(part, to='name_short')
            if country_name and country_name != 'not found':
                result["country"] = country_name
                result["country_code"] = cc.convert(part, to='ISO3')
                continue
        except:
            pass

        # If not a state or country, assume it's a city
        if not result["city"]:
            result["city"] = part

    # If we found a US state but no country was explicitly set, mark as USA
    if result["state"] and not result["country"]:
        result["country"] = "United States"
        result["country_code"] = "USA"

    return result


def locations_match(location1: str, location2: str) -> bool:
    """
    Check if two location strings match, accounting for:
    - US state names vs abbreviations
    - Country name variations
    - Partial city matches
    - Case insensitivity
    """
    if not location1 or not location2:
        return False

    # Normalize both locations
    norm1 = normalize_location(location1)
    norm2 = normalize_location(location2)

    # Direct string match (case insensitive)
    if norm1["original"].lower() == norm2["original"].lower():
        return True

    # Check country match
    if norm1["country"] and norm2["country"]:
        if norm1["country"].lower() == norm2["country"].lower():
            # If both have countries and they match, check if states match (if applicable)
            if norm1["state"] and norm2["state"]:
                return norm1["state"].lower() == norm2["state"].lower()
            # If only one has a state, we still consider it a match (country level)
            return True
        # Different countries = no match
        return False

    # Check US state match (by name or abbreviation)
    if norm1["state"] and norm2["state"]:
        return norm1["state"].lower() == norm2["state"].lower()

    # Check if one is a state and the other mentions USA
    if norm1["state"] and norm2["country"] and "united states" in norm2["country"].lower():
        return True
    if norm2["state"] and norm1["country"] and "united states" in norm1["country"].lower():
        return True

    # Check city partial match
    if norm1["city"] and norm2["city"]:
        city1_lower = norm1["city"].lower()
        city2_lower = norm2["city"].lower()
        # Partial match: one city name contains the other
        if city1_lower in city2_lower or city2_lower in city1_lower:
            return True

    # Check if any part of one location appears in the other (partial match)
    loc1_lower = norm1["original"].lower()
    loc2_lower = norm2["original"].lower()

    # Split into words and check for significant word overlap
    words1 = set(re.split(r'[\s,;/\-]+', loc1_lower))
    words2 = set(re.split(r'[\s,;/\-]+', loc2_lower))

    # Remove very short words (like state abbreviations might be too generic)
    words1 = {w for w in words1 if len(w) > 1}
    words2 = {w for w in words2 if len(w) > 1}

    # If there's significant overlap (at least one meaningful word)
    overlap = words1.intersection(words2)
    if overlap:
        return True

    return False


def filter_candidates_by_location(candidates: list[dict], location_filter: str) -> list[dict]:
    """
    Filter a list of candidates by location(s).

    Args:
        candidates: List of candidate dictionaries from Lever API
        location_filter: Location string(s) to filter by.
                        Can be a single location or multiple locations separated by newlines.
                        Examples: "California", "California\nNew York\nTexas"

    Returns:
        Filtered list of candidates matching any of the specified locations
    """
    if not location_filter or not location_filter.strip():
        return candidates

    location_filter = location_filter.strip()

    # Split by newlines to support multiple locations (one per line)
    location_filters = [loc.strip() for loc in location_filter.split('\n') if loc.strip()]

    filtered = []

    for candidate in candidates:
        # Get candidate location from Lever data
        # Lever stores location in different possible fields
        candidate_location = None

        # Check common location fields
        if "location" in candidate and candidate["location"]:
            candidate_location = candidate["location"]
        elif "locations" in candidate and candidate["locations"]:
            # Some APIs return an array of locations
            locations = candidate["locations"]
            if isinstance(locations, list) and locations:
                candidate_location = locations[0]
            else:
                candidate_location = locations

        # If no location field, check if it's in other fields
        if not candidate_location:
            # Check if there's a contact field with location
            contact = candidate.get("contact", {})
            if isinstance(contact, dict):
                candidate_location = contact.get("location")

        # Convert to string if needed
        if candidate_location and not isinstance(candidate_location, str):
            candidate_location = str(candidate_location)

        # If candidate has a location, check if it matches ANY of the filters
        if candidate_location:
            for filter_loc in location_filters:
                if locations_match(candidate_location, filter_loc):
                    filtered.append(candidate)
                    break  # Don't add the same candidate multiple times
        # If no location data, we might want to include them (configurable)
        # For now, we exclude candidates without location data

    return filtered
