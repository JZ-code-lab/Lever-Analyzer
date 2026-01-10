import re
from typing import Optional
import country_converter as coco
import us
import phonenumbers
from phonenumbers import geocoder
import logging

# Suppress country_converter warnings/errors
logging.getLogger('country_converter').setLevel(logging.CRITICAL)

# Region mappings for common geographic areas
REGION_MAPPINGS = {
    "bay area": [
        # San Francisco Peninsula
        "san francisco", "daly city", "south san francisco", "san bruno",
        "millbrae", "burlingame", "san mateo", "foster city", "belmont",
        "san carlos", "redwood city", "menlo park", "palo alto",
        # East Bay
        "oakland", "berkeley", "alameda", "emeryville", "albany",
        "el cerrito", "richmond", "san pablo", "pinole", "hercules",
        "martinez", "concord", "walnut creek", "pleasant hill", "clayton",
        "danville", "san ramon", "dublin", "pleasanton", "livermore",
        "fremont", "newark", "union city", "hayward", "san leandro",
        "castro valley", "san lorenzo",
        # South Bay / Silicon Valley
        "san jose", "santa clara", "sunnyvale", "mountain view", "los altos",
        "cupertino", "saratoga", "campbell", "los gatos", "monte sereno",
        "milpitas", "santa teresa", "willow glen",
        # North Bay
        "san rafael", "novato", "petaluma", "santa rosa", "rohnert park",
        "cotati", "sebastopol", "healdsburg", "windsor", "cloverdale",
        "vallejo", "benicia", "fairfield", "vacaville", "suisun city",
        "napa", "american canyon", "st helena", "calistoga", "yountville",
        "sausalito", "mill valley", "tiburon", "corte madera", "larkspur",
        "san anselmo", "fairfax"
    ],
    "silicon valley": [
        "san jose", "palo alto", "mountain view", "sunnyvale", "santa clara",
        "cupertino", "milpitas", "los altos", "redwood city", "menlo park",
        "campbell", "saratoga", "los gatos"
    ],
    "greater los angeles": [
        "los angeles", "santa monica", "pasadena", "glendale", "burbank",
        "long beach", "anaheim", "irvine", "santa ana", "torrance",
        "inglewood", "el segundo", "culver city", "beverly hills"
    ],
    "orange county": [
        "santa ana", "anaheim", "irvine", "huntington beach", "garden grove",
        "orange", "fullerton", "costa mesa", "mission viejo", "newport beach",
        "tustin", "lake forest", "yorba linda", "laguna niguel"
    ],
    "greater seattle": [
        # Seattle proper
        "seattle",
        # Eastside (King County)
        "bellevue", "redmond", "kirkland", "sammamish", "issaquah",
        "mercer island", "newcastle", "woodinville", "bothell", "kenmore",
        "lake forest park", "shoreline", "mountlake terrace", "brier",
        # South King County
        "renton", "kent", "auburn", "federal way", "tukwila", "seatac",
        "burien", "des moines", "covington", "maple valley", "enumclaw",
        # North (Snohomish County)
        "everett", "lynnwood", "edmonds", "mukilteo", "mill creek",
        "marysville", "lake stevens", "snohomish", "monroe", "arlington",
        # South Sound (Pierce County)
        "tacoma", "lakewood", "puyallup", "university place", "bonney lake",
        "sumner", "edgewood", "fife", "gig harbor", "dupont", "steilacoom",
        # West (Kitsap County - across Puget Sound)
        "bremerton", "silverdale", "poulsbo", "port orchard", "bainbridge island"
    ],
    "seattle metro": [  # Alias
        "seattle", "bellevue", "redmond", "kirkland", "sammamish", "issaquah",
        "mercer island", "newcastle", "woodinville", "bothell", "kenmore",
        "lake forest park", "shoreline", "mountlake terrace", "brier",
        "renton", "kent", "auburn", "federal way", "tukwila", "seatac",
        "burien", "des moines", "covington", "maple valley", "enumclaw",
        "everett", "lynnwood", "edmonds", "mukilteo", "mill creek",
        "marysville", "lake stevens", "snohomish", "monroe", "arlington",
        "tacoma", "lakewood", "puyallup", "university place", "bonney lake",
        "sumner", "edgewood", "fife", "gig harbor", "dupont", "steilacoom",
        "bremerton", "silverdale", "poulsbo", "port orchard", "bainbridge island"
    ],
    "greater boston": [
        "boston", "cambridge", "somerville", "brookline", "newton", "quincy",
        "waltham", "framingham", "malden", "medford", "lynn", "arlington"
    ],
    "dmv": [  # DC-Maryland-Virginia
        "washington", "arlington", "alexandria", "bethesda", "silver spring",
        "rockville", "falls church", "tysons", "mclean", "reston", "fairfax"
    ],
    "nyc metro": [  # New York City Metro area - includes NJ
        "new york", "brooklyn", "manhattan", "queens", "bronx", "staten island",
        "newark", "jersey city", "hoboken", "weehawken", "edgewater",
        "fort lee", "hackensack", "paterson", "elizabeth", "bayonne",
        "yonkers", "white plains", "new rochelle", "mount vernon"
    ],
    "new york metro": [  # Alias for NYC metro
        "new york", "brooklyn", "manhattan", "queens", "bronx", "staten island",
        "newark", "jersey city", "hoboken", "weehawken", "edgewater",
        "fort lee", "hackensack", "paterson", "elizabeth", "bayonne",
        "yonkers", "white plains", "new rochelle", "mount vernon"
    ],
    "tri-state": [  # NY-NJ-CT area
        "new york", "newark", "jersey city", "yonkers", "bridgeport",
        "stamford", "white plains", "hoboken", "paterson", "new haven",
        "norwalk", "danbury"
    ],
    "chicago metro": [
        "chicago", "naperville", "aurora", "joliet", "rockford", "elgin",
        "cicero", "arlington heights", "evanston", "schaumburg", "bolingbrook"
    ],
    "dallas metro": [
        "dallas", "fort worth", "arlington", "plano", "irving", "garland",
        "frisco", "mckinney", "richardson", "carrollton", "denton"
    ],
    "houston metro": [
        "houston", "sugar land", "the woodlands", "pearland", "league city",
        "baytown", "missouri city", "texas city", "pasadena", "conroe"
    ],
    "atlanta metro": [
        "atlanta", "sandy springs", "roswell", "marietta", "johns creek",
        "alpharetta", "smyrna", "dunwoody", "brookhaven", "peachtree city"
    ],
    "phoenix metro": [
        "phoenix", "mesa", "chandler", "scottsdale", "glendale", "gilbert",
        "tempe", "peoria", "surprise", "avondale", "goodyear"
    ],
    "philadelphia metro": [
        "philadelphia", "camden", "wilmington", "cherry hill", "trenton",
        "bensalem", "gloucester", "king of prussia", "norristown"
    ],
    "miami metro": [
        "miami", "fort lauderdale", "west palm beach", "hialeah", "boca raton",
        "miami beach", "coral springs", "pembroke pines", "hollywood", "doral"
    ],
    "denver metro": [
        "denver", "aurora", "lakewood", "centennial", "boulder", "arvada",
        "westminster", "thornton", "broomfield", "longmont", "castle rock"
    ],
    "portland metro": [
        "portland", "vancouver", "gresham", "hillsboro", "beaverton", "bend",
        "salem", "eugene", "tigard", "lake oswego"
    ],
    "austin metro": [
        "austin", "round rock", "georgetown", "pflugerville", "cedar park",
        "san marcos", "kyle", "buda", "leander", "hutto"
    ]
}


def expand_region(location: str) -> list[str]:
    """
    Expand a region name into its constituent cities.

    Args:
        location: Location string that might be a region name

    Returns:
        List of cities in the region, or [location] if not a recognized region
    """
    location_lower = location.lower().strip()

    # Check if this is a known region
    for region_name, cities in REGION_MAPPINGS.items():
        if region_name in location_lower:
            return cities

    # Not a region, return as-is
    return [location]


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

        # Check if it's a country (skip obvious non-countries)
        # Only check if it's a reasonable country name (no spaces, not a common US city)
        if ' ' not in part and part.lower() not in ['san', 'los', 'new', 'fort', 'saint', 'mount']:
            try:
                country_name = cc.convert(part, to='name_short')
                if country_name and country_name != 'not found':
                    result["country"] = country_name
                    result["country_code"] = cc.convert(part, to='ISO3')
                    continue
            except Exception:
                pass

        # If not a state or country, assume it's a city
        if not result["city"]:
            result["city"] = part

    # If we found a US state but no country was explicitly set, mark as USA
    if result["state"] and not result["country"]:
        result["country"] = "United States"
        result["country_code"] = "USA"

    return result


def locations_match(location1: str, location2: str, _expanded: bool = False) -> bool:
    """
    Check if two location strings match, accounting for:
    - Regional areas (e.g., "Bay Area" matches "San Francisco", "Oakland", etc.)
    - US state names vs abbreviations
    - Country name variations
    - Partial city matches
    - Case insensitivity
    """
    if not location1 or not location2:
        return False

    # Check if location1 is a region - if so, expand it to cities
    # Only do this on first call to avoid infinite recursion
    if not _expanded:
        expanded_locations = expand_region(location1)

        # If location1 was expanded to multiple cities, check if location2 matches any of them
        if len(expanded_locations) > 1:
            for city in expanded_locations:
                if locations_match(city, location2, _expanded=True):
                    return True
            # If no city matched, fall through to try matching the original region name

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


def extract_phone_numbers(text: str) -> list[str]:
    """
    Extract phone numbers from text.

    Args:
        text: Text that may contain phone numbers

    Returns:
        List of phone numbers found (as strings)
    """
    if not text:
        return []

    # Limit search to first 2000 characters for performance
    search_text = text[:2000]

    phone_numbers = []

    # Common phone number patterns
    patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890 or 1234567890
        r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',     # (123) 456-7890
        r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # +1-123-456-7890
    ]

    for pattern in patterns:
        matches = re.findall(pattern, search_text)
        phone_numbers.extend(matches)
        # Stop after finding the first phone number for performance
        if phone_numbers:
            break

    return phone_numbers


def get_location_from_phone_number(phone_number: str) -> Optional[str]:
    """
    Infer location from phone number area code.

    Args:
        phone_number: Phone number string

    Returns:
        Location string (city, state) or None if unable to determine
    """
    if not phone_number:
        return None

    try:
        # Clean the phone number
        phone_clean = re.sub(r'[^\d+]', '', phone_number)

        # If it doesn't start with +, assume US and add +1
        if not phone_clean.startswith('+'):
            phone_clean = '+1' + phone_clean

        # Parse the phone number
        parsed = phonenumbers.parse(phone_clean, None)

        # Get the location description
        location = geocoder.description_for_number(parsed, "en")

        if location:
            return location

    except Exception:
        pass

    return None


def extract_location_from_resume(resume_text: str) -> Optional[str]:
    """
    Extract location from resume text.
    Looks for:
    1. Explicit location patterns (City, State format)
    2. Addresses with city/state/zip
    3. Company locations

    Args:
        resume_text: The full resume text

    Returns:
        Location string if found, None otherwise
    """
    if not resume_text:
        return None

    # Limit search to first 2000 characters (header section) for performance
    # Most resumes have location at the top
    search_text = resume_text[:2000]

    # Pattern 1: City, State (full name or abbreviation) with optional ZIP
    # Examples: "San Francisco, CA", "New York, New York 10001"
    # Made more efficient by using non-greedy quantifiers and atomic groups
    city_state_pattern = r'\b([A-Z][a-zA-Z ]{1,30}?),\s*([A-Z]{2}|[A-Z][a-zA-Z ]{1,20}?)(?:\s+\d{5})?\b'

    matches = re.findall(city_state_pattern, search_text)

    if matches:
        # Return the first match, which is usually the candidate's location
        # (typically at the top of resume)
        city, state = matches[0]
        return f"{city.strip()}, {state.strip()}"

    # Pattern 2: Look for location keywords followed by city/state
    # Examples: "Location: San Francisco, CA", "Based in Seattle, WA"
    location_keyword_pattern = r'(?:Location|Based in|Residing in|Address):\s*([A-Z][a-zA-Z ]{1,30}?,\s*[A-Z]{2})'

    keyword_match = re.search(location_keyword_pattern, search_text, re.IGNORECASE)
    if keyword_match:
        return keyword_match.group(1).strip()

    return None


def get_candidate_location_multi_source(candidate: dict, resume_text: Optional[str] = None) -> Optional[str]:
    """
    Get candidate location from multiple sources in priority order:
    1. Lever location field
    2. Resume text (extracted location)
    3. Phone number area code

    Args:
        candidate: Candidate dictionary from Lever API
        resume_text: Optional resume text

    Returns:
        Location string or None
    """
    # Source 1: Lever location field
    candidate_location = None

    if "location" in candidate and candidate["location"]:
        candidate_location = candidate["location"]
    elif "locations" in candidate and candidate["locations"]:
        locations = candidate["locations"]
        if isinstance(locations, list) and locations:
            candidate_location = locations[0]
        else:
            candidate_location = locations

    # Check contact field with location
    if not candidate_location:
        contact = candidate.get("contact", {})
        if isinstance(contact, dict):
            candidate_location = contact.get("location")

    # Convert to string if needed
    if candidate_location and not isinstance(candidate_location, str):
        candidate_location = str(candidate_location)

    if candidate_location and candidate_location.strip():
        return candidate_location.strip()

    # Source 2: Resume text
    if resume_text:
        resume_location = extract_location_from_resume(resume_text)
        if resume_location:
            return resume_location

    # Source 3: Phone number area code
    # Check Lever data for phone numbers
    phone_numbers = []

    # Get phones from candidate data
    if "phones" in candidate:
        phones = candidate["phones"]
        if isinstance(phones, list):
            for phone_obj in phones:
                if isinstance(phone_obj, dict):
                    phone_numbers.append(phone_obj.get("value", ""))
                else:
                    phone_numbers.append(str(phone_obj))
        elif phones:
            phone_numbers.append(str(phones))

    # Also check contact field
    contact = candidate.get("contact", {})
    if isinstance(contact, dict) and "phone" in contact:
        phone_numbers.append(str(contact["phone"]))

    # Extract phones from resume text
    if resume_text:
        resume_phones = extract_phone_numbers(resume_text)
        phone_numbers.extend(resume_phones)

    # Try to get location from first valid phone number
    for phone in phone_numbers:
        if phone and phone.strip():
            location = get_location_from_phone_number(phone.strip())
            if location:
                return location

    return None


def filter_candidates_by_location(candidates: list[dict], location_filter: str, resume_texts: Optional[dict] = None) -> list[dict]:
    """
    Filter a list of candidates by location(s) using multi-source detection.

    Args:
        candidates: List of candidate dictionaries from Lever API
        location_filter: Location string(s) to filter by.
                        Can be a single location or multiple locations separated by newlines.
                        Examples: "California", "California\nNew York\nTexas"
        resume_texts: Optional dict mapping candidate IDs to resume text for enhanced location detection

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
        # Get resume text if available
        resume_text = None
        if resume_texts and candidate.get("id") in resume_texts:
            resume_text = resume_texts[candidate["id"]]

        # Use multi-source location detection (Lever field, resume, phone)
        candidate_location = get_candidate_location_multi_source(candidate, resume_text)

        # If candidate has a location, check if it matches ANY of the filters
        if candidate_location:
            for filter_loc in location_filters:
                # Important: filter_loc must be first parameter so regions get expanded correctly
                if locations_match(filter_loc, candidate_location):
                    filtered.append(candidate)
                    break  # Don't add the same candidate multiple times
        # If no location data found from any source, exclude the candidate

    return filtered


def filter_candidates_with_resumes_by_location(candidates_with_resumes: list[dict], location_filter: str, progress_callback=None) -> list[dict]:
    """
    Filter candidates_with_resumes by location using multi-source detection.

    Args:
        candidates_with_resumes: List of dicts with 'candidate' and 'resume_text' keys
        location_filter: Location string(s) to filter by (newline-separated)
        progress_callback: Optional callback function(current, total) for progress updates

    Returns:
        Filtered list of candidates_with_resumes matching any of the specified locations
    """
    if not location_filter or not location_filter.strip():
        return candidates_with_resumes

    location_filter = location_filter.strip()

    # Split by newlines to support multiple locations (one per line)
    location_filters = [loc.strip() for loc in location_filter.split('\n') if loc.strip()]

    # Pre-expand all filter locations (to avoid re-expanding for every candidate)
    expanded_filters = []
    for filter_loc in location_filters:
        expanded = expand_region(filter_loc)
        if len(expanded) > 1:
            # This was a region, store all expanded cities
            expanded_filters.extend([(city, True) for city in expanded])
        else:
            # Not a region, store as-is
            expanded_filters.append((filter_loc, False))

    filtered = []
    total = len(candidates_with_resumes)

    for idx, item in enumerate(candidates_with_resumes):
        # Report progress
        if progress_callback and idx % 5 == 0:  # Update every 5 candidates
            progress_callback(idx, total)

        candidate = item["candidate"]
        resume_text = item.get("resume_text")

        # Use multi-source location detection (Lever field, resume, phone)
        candidate_location = get_candidate_location_multi_source(candidate, resume_text)

        # If candidate has a location, check if it matches ANY of the filters
        if candidate_location:
            for filter_loc, is_expanded in expanded_filters:
                # Use _expanded=True when checking expanded cities to avoid re-expansion
                if locations_match(filter_loc, candidate_location, _expanded=is_expanded):
                    filtered.append(item)
                    break  # Don't add the same item multiple times
        # If no location data found from any source, exclude the candidate

    # Final progress update
    if progress_callback:
        progress_callback(total, total)

    return filtered
