import re
from typing import Optional
from functools import lru_cache
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


# US area code -> representative "City, ST". Used as the last-resort
# location source when Lever and the resume have no usable location.
# libphonenumber's geocoder only returns state-level for US numbers, which
# is too coarse to match a city/region filter, so we map the major metros
# explicitly. Each value is a city that lives inside the relevant
# REGION_MAPPINGS entry so it flows through region matching correctly.
US_AREA_CODE_LOCATIONS = {
    # San Francisco Bay Area
    "415": "San Francisco, CA", "628": "San Francisco, CA",
    "510": "Oakland, CA", "341": "Oakland, CA",
    "650": "Palo Alto, CA",
    "408": "San Jose, CA", "669": "San Jose, CA",
    "925": "Walnut Creek, CA",
    "707": "Santa Rosa, CA",
    # Sacramento (not Bay Area — correctly excluded by a Bay filter)
    "916": "Sacramento, CA", "279": "Sacramento, CA",
    # Greater Los Angeles
    "213": "Los Angeles, CA", "323": "Los Angeles, CA", "310": "Los Angeles, CA",
    "424": "Los Angeles, CA", "818": "Los Angeles, CA", "747": "Los Angeles, CA",
    "661": "Los Angeles, CA", "626": "Pasadena, CA", "562": "Long Beach, CA",
    # Orange County
    "714": "Santa Ana, CA", "657": "Santa Ana, CA", "949": "Irvine, CA",
    # San Diego
    "619": "San Diego, CA", "858": "San Diego, CA", "760": "San Diego, CA",
    "442": "San Diego, CA",
    # Seattle metro
    "206": "Seattle, WA", "425": "Bellevue, WA", "253": "Tacoma, WA",
    # NYC metro
    "212": "New York, NY", "646": "New York, NY", "332": "New York, NY",
    "917": "New York, NY", "718": "Brooklyn, NY", "347": "Brooklyn, NY",
    "929": "Queens, NY", "201": "Jersey City, NJ", "551": "Jersey City, NJ",
    "973": "Newark, NJ", "862": "Newark, NJ",
    # Greater Boston
    "617": "Boston, MA", "857": "Boston, MA",
    # DC metro
    "202": "Washington, DC", "703": "Arlington, VA", "571": "Arlington, VA",
    # Chicago metro
    "312": "Chicago, IL", "872": "Chicago, IL", "773": "Chicago, IL",
    # Dallas metro
    "214": "Dallas, TX", "469": "Dallas, TX", "972": "Dallas, TX",
    "817": "Fort Worth, TX", "682": "Fort Worth, TX",
    # Houston metro
    "713": "Houston, TX", "281": "Houston, TX", "832": "Houston, TX",
    "346": "Houston, TX",
    # Austin metro
    "512": "Austin, TX", "737": "Austin, TX",
    # Atlanta metro
    "404": "Atlanta, GA", "470": "Atlanta, GA", "678": "Atlanta, GA",
    "770": "Atlanta, GA",
    # Phoenix metro
    "602": "Phoenix, AZ", "480": "Phoenix, AZ", "623": "Phoenix, AZ",
    # Philadelphia metro
    "215": "Philadelphia, PA", "267": "Philadelphia, PA", "445": "Philadelphia, PA",
    # Miami metro
    "305": "Miami, FL", "786": "Miami, FL",
    # Denver metro
    "303": "Denver, CO", "720": "Denver, CO",
    # Portland metro
    "503": "Portland, OR", "971": "Portland, OR",
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


@lru_cache(maxsize=1024)
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
        # Only accept exact matches or 2-letter abbreviations to avoid false positives
        state = us.states.lookup(part)
        if state:
            # Verify it's an exact match (case-insensitive) or a 2-letter abbreviation
            is_exact_name = state.name.lower() == part.lower()
            is_abbr = len(part) == 2 and state.abbr.lower() == part.lower()
            if is_exact_name or is_abbr:
                result["state"] = state.name
                result["state_abbr"] = state.abbr
                result["country"] = "United States"
                result["country_code"] = "USA"
                continue

        # Check if it's a country
        # Skip obvious city name prefixes, but allow spaces in country names
        if part.lower() not in ['san', 'los', 'new', 'fort', 'saint', 'mount']:
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


def locations_match(filter_location: str, candidate_location: str, _expanded: bool = False) -> bool:
    """
    Return True if `candidate_location` falls within `filter_location`.

    Matching is anchored to the MOST SPECIFIC component the FILTER provides:
      - region  -> candidate must be in one of the region's constituent cities
      - city    -> candidate's city must be that city (states must agree if both given)
      - state   -> candidate's state must match (filter gave no city)
      - country -> candidate's country must match (filter gave no city/state)

    This is the key correctness rule: a city or region filter (e.g.
    "San Jose, CA" or "San Francisco Bay Area") must NOT match every
    candidate in the same state (Los Angeles, San Diego, etc.). It only
    falls back to state/country matching when the filter itself is
    specified only at that level.
    """
    if not filter_location or not candidate_location:
        return False

    # If the filter is a known region, the candidate must be in one of its
    # constituent cities. Being in the same STATE is NOT being in the region,
    # so there is deliberately no looser fallback here.
    if not _expanded:
        expanded = expand_region(filter_location)
        if len(expanded) > 1:
            for city in expanded:
                if locations_match(city, candidate_location, _expanded=True):
                    return True
            return False

    norm_f = normalize_location(filter_location)
    norm_c = normalize_location(candidate_location)

    # Exact original-string match (case-insensitive)
    if norm_f["original"].lower().strip() == norm_c["original"].lower().strip():
        return True

    # 1) Filter specifies a CITY -> candidate must be in that same city.
    if norm_f["city"]:
        if not norm_c["city"]:
            return False
        fc = norm_f["city"].lower().strip()
        cc_ = norm_c["city"].lower().strip()
        # Same city, or one city string contains the other (handles
        # "San Jose" vs "Greater San Jose Area"). NOT a state/word fallback.
        if fc == cc_ or fc in cc_ or cc_ in fc:
            # If both sides also carry a state, the states must agree
            # (guards against same-named cities, e.g. Portland OR vs ME).
            if norm_f["state"] and norm_c["state"]:
                return norm_f["state"].lower() == norm_c["state"].lower()
            return True
        return False

    # 2) Filter specifies only a STATE -> candidate's state must match.
    if norm_f["state"]:
        if norm_c["state"]:
            return norm_f["state"].lower() == norm_c["state"].lower()
        return False

    # 3) Filter specifies only a COUNTRY -> candidate's country must match.
    if norm_f["country"]:
        if norm_c["country"]:
            return norm_f["country"].lower() == norm_c["country"].lower()
        return False

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

        # Pull just the digits and normalize a US 11-digit (1 + 10) down to 10.
        digits = re.sub(r'\D', '', phone_clean)
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]

        # US number: map the 3-digit area code to a representative city.
        # This is the meaningful signal for city/region filters; do it
        # BEFORE libphonenumber, whose US geocoding is only state-level.
        if len(digits) == 10:
            area_code = digits[:3]
            mapped = US_AREA_CODE_LOCATIONS.get(area_code)
            if mapped:
                return mapped

        # Fallback: libphonenumber geocoder (handles international numbers
        # and gives state-level info for US area codes not in our map).
        if not phone_clean.startswith('+'):
            phone_clean = '+1' + phone_clean
        parsed = phonenumbers.parse(phone_clean, None)
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

    # Also check the (expanded) contact object. Lever's Contact carries a
    # `phones` list ([{value, type}, ...]); older code only looked for a
    # singular `phone`, so contact phone numbers were being missed.
    contact = candidate.get("contact", {})
    if isinstance(contact, dict):
        contact_phones = contact.get("phones")
        if isinstance(contact_phones, list):
            for phone_obj in contact_phones:
                if isinstance(phone_obj, dict):
                    phone_numbers.append(phone_obj.get("value", ""))
                else:
                    phone_numbers.append(str(phone_obj))
        if contact.get("phone"):
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


def filter_candidates_by_location_fast(candidates: list[dict], location_filter: str) -> tuple[list[dict], list[dict]]:
    """
    Fast filter using only Lever location field (no resume parsing).
    Returns candidates that match OR need resume check (vague/no location).

    Args:
        candidates: List of candidate dictionaries from Lever API
        location_filter: Location string(s) to filter by (newline-separated)

    Returns:
        Tuple of (matched_candidates, needs_resume_check_candidates)
        - matched_candidates: Candidates whose Lever location exactly matches the filter
        - needs_resume_check_candidates: Candidates with no/vague location or same country/state
    """
    if not location_filter or not location_filter.strip():
        return candidates, []

    location_filter = location_filter.strip()

    # Split by newlines to support multiple locations
    location_filters = [loc.strip() for loc in location_filter.split('\n') if loc.strip()]

    # Normalize all filter locations to understand what we're filtering for
    filter_locations_normalized = [normalize_location(f) for f in location_filters]

    # Pre-expand all filter locations and normalize them for fast lookup
    expanded_filters = []
    expanded_cities_lower = set()  # For fast city name lookup
    for filter_loc in location_filters:
        expanded = expand_region(filter_loc)
        if len(expanded) > 1:
            # Region expanded to multiple cities - add all to fast lookup set
            for city in expanded:
                expanded_cities_lower.add(city.lower())
                expanded_filters.append((city, True))
        else:
            expanded_filters.append((filter_loc, False))

    matched = []
    needs_resume_check = []

    for candidate in candidates:
        # Get location from Lever field only (no resume parsing)
        candidate_location = None
        if "location" in candidate and candidate["location"]:
            candidate_location = candidate["location"]
        elif "locations" in candidate and candidate["locations"]:
            locations = candidate["locations"]
            if isinstance(locations, list) and locations:
                candidate_location = locations[0]
            else:
                candidate_location = locations
        elif "contact" in candidate and isinstance(candidate.get("contact"), dict):
            candidate_location = candidate["contact"].get("location")

        # Convert to string if needed
        if candidate_location and not isinstance(candidate_location, str):
            candidate_location = str(candidate_location)

        if not candidate_location or not candidate_location.strip():
            # No location in Lever - MUST check resume
            needs_resume_check.append(candidate)
            continue

        # Normalize candidate location once
        candidate_norm = normalize_location(candidate_location)

        # OPTIMIZATION: For region filters (like Bay Area with 80 cities), use fast set lookup
        # instead of calling locations_match 80 times
        is_match = False

        # Quick check: if candidate has a city and it's in our expanded cities set, it's a match
        if candidate_norm["city"] and expanded_cities_lower:
            candidate_city_lower = candidate_norm["city"].lower()
            if candidate_city_lower in expanded_cities_lower:
                matched.append(candidate)
                is_match = True
                continue

        # If not a quick match, do full matching (for non-expanded filters or edge cases)
        if not is_match:
            for filter_loc, is_expanded in expanded_filters:
                # Skip expanded filters if we already checked via set lookup
                if is_expanded and expanded_cities_lower:
                    continue
                if locations_match(filter_loc, candidate_location, _expanded=is_expanded):
                    matched.append(candidate)
                    is_match = True
                    break

        if is_match:
            continue

        # Not an exact match - but should we check their resume?
        # Include for resume check if:
        # 1. Candidate location is vague (just country or just state)
        # 2. Candidate is in same country/state as any filter
        should_check_resume = False

        # Check if candidate location is vague (just country or just state, no city)
        if not candidate_norm["city"] and (candidate_norm["country"] or candidate_norm["state"]):
            should_check_resume = True
        else:
            # Check if candidate is in same country/state as any filter
            for filter_norm in filter_locations_normalized:
                # Same country
                if (candidate_norm["country"] and filter_norm["country"] and
                    candidate_norm["country"].lower() == filter_norm["country"].lower()):
                    # If filter has a state, check if same state
                    if filter_norm["state"]:
                        if candidate_norm["state"] and candidate_norm["state"].lower() == filter_norm["state"].lower():
                            should_check_resume = True
                            break
                    else:
                        # Filter only specified country, include all from that country for resume check
                        should_check_resume = True
                        break

        if should_check_resume:
            needs_resume_check.append(candidate)
        # else: exclude this candidate (different country/state, not worth checking resume)

    return matched, needs_resume_check


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
