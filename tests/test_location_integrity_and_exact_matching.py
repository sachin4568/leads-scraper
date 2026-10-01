from __future__ import annotations

import pytest
from backend.app.ingestion.canonical_location import (
    CanonicalLocation,
    LocationValidationResult,
    LocationValidator,
)
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.sources.google_maps import GoogleMapsConnector
from backend.app.sources.osm_overpass import OSMOverpassConnector
from backend.app.ingestion.identity import CanonicalIdentityEngine
from backend.app.ingestion.ingestion import RawLead
from backend.app.models_phase2 import CanonicalLead


def test_1_uk_england_manchester_accept():
    """TEST 1: Requested UK + England + Manchester -> Candidate Manchester, Greater Manchester, UK -> ACCEPT"""
    is_valid, err, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
    )
    assert is_valid is True
    assert scope is not None
    assert scope.country_code == "GB"
    assert scope.country == "United Kingdom"
    assert scope.region == "England"

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_1",
        business_name="Manchester City Auto Repairs",
        address="Unit 4, Redcote Lane, Manchester, Greater Manchester, M12 5PW, UK",
        city="Manchester",
        state="Greater Manchester",
        country="United Kingdom",
        country_code="GB",
        latitude=53.475,
        longitude=-2.215,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.country_match is True
    assert result.city_match is True
    assert result.rejection_reason is None


def test_2_uk_england_manchester_reject_usa():
    """TEST 2: Requested UK + England + Manchester -> Candidate Manchester, Connecticut, USA -> REJECT"""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
    )

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_2",
        business_name="Manchester CT Auto Center",
        address="123 Main St, Manchester, CT 06040, USA",
        city="Manchester",
        state="Connecticut",
        country="United States",
        country_code="US",
        latitude=41.775,
        longitude=-72.521,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.country_match is False
    assert result.rejection_reason == "LOCATION_COUNTRY_MISMATCH"


def test_3_uk_england_manchester_reject_birmingham():
    """TEST 3: Requested UK + England + Manchester -> Candidate Birmingham, UK -> REJECT"""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
    )

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_3",
        business_name="Birmingham Central Garage",
        address="10 New St, Birmingham, West Midlands, B2 4BF, UK",
        city="Birmingham",
        state="West Midlands",
        country="United Kingdom",
        country_code="GB",
        latitude=52.480,
        longitude=-1.898,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.country_match is True
    assert result.rejection_reason in ("LOCATION_CITY_MISMATCH", "LOCATION_CITY_BOUNDARY_MISMATCH")


def test_4_uk_northern_ireland_manchester_invalid_configuration():
    """TEST 4: Requested UK + Northern Ireland + Manchester -> INVALID CONFIGURATION (Scrape should NOT start)"""
    is_valid, err_msg, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="Northern Ireland",
        city="Manchester",
    )
    assert is_valid is False
    assert scope is None
    assert err_msg is not None
    assert "Manchester is in England, not Northern Ireland" in err_msg


def test_5_usa_connecticut_manchester_accept():
    """TEST 5: Requested United States + Connecticut + Manchester -> Candidate Manchester, CT, USA -> ACCEPT"""
    is_valid, err, scope = LocationValidator.validate_requested_configuration(
        country="United States",
        region="Connecticut",
        city="Manchester",
    )
    assert is_valid is True
    assert scope is not None
    assert scope.country_code == "US"
    assert scope.region == "Connecticut"

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_5",
        business_name="Manchester Auto Repair",
        address="45 Broad St, Manchester, CT 06040, USA",
        city="Manchester",
        state="Connecticut",
        country="United States",
        country_code="US",
        latitude=41.776,
        longitude=-72.520,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.country_match is True


def test_6_uk_london_reject_canada_london():
    """TEST 6: Requested United Kingdom + London -> Candidate London, Ontario, Canada -> REJECT"""
    is_valid, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="London",
    )
    assert is_valid is True

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_6",
        business_name="London Ontario Brakes",
        address="789 Dundas St, London, ON N5W 2Z6, Canada",
        city="London",
        state="Ontario",
        country="Canada",
        country_code="CA",
        latitude=42.990,
        longitude=-81.230,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is False
    assert result.country_match is False
    assert result.rejection_reason == "LOCATION_COUNTRY_MISMATCH"


def test_7_india_delhi_accept():
    """TEST 7: Requested India + Delhi -> Candidate Delhi, India -> ACCEPT"""
    is_valid, _, scope = LocationValidator.validate_requested_configuration(
        country="India",
        region="Delhi",
        city="Delhi",
    )
    assert is_valid is True
    assert scope.country_code == "IN"

    candidate = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="node/12345",
        business_name="Delhi Car Care",
        address="Connaught Place, New Delhi, Delhi 110001, India",
        city="Delhi",
        state="Delhi",
        country="India",
        country_code="IN",
        latitude=28.631,
        longitude=77.219,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is True
    assert result.country_match is True


def test_8_india_delhi_reject_delhi_ny_usa():
    """TEST 8: Requested India + Delhi -> Candidate Delhi, New York, USA -> REJECT"""
    is_valid, _, scope = LocationValidator.validate_requested_configuration(
        country="India",
        region="Delhi",
        city="Delhi",
    )
    assert is_valid is True

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_8",
        business_name="Delhi Village Motors",
        address="1 Main St, Delhi, NY 13753, USA",
        city="Delhi",
        state="New York",
        country="United States",
        country_code="US",
        latitude=42.278,
        longitude=-74.916,
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is False
    assert result.country_match is False
    assert result.rejection_reason == "LOCATION_COUNTRY_MISMATCH"


def test_9_insufficient_evidence_reject():
    """TEST 9: Candidate has no reliable geographic information -> REJECT (INSUFFICIENT_EVIDENCE)"""
    is_valid, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
    )

    candidate = NormalizedLeadRecord(
        source="custom_scrape",
        source_id="item_9",
        business_name="Ghost Motors",
        address=None,
        phone=None,
        website=None,
        latitude=None,
        longitude=None,
        raw_data={},
    )

    result = LocationValidator.evaluate_candidate(candidate, scope)
    assert result.is_valid is False
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.rejection_reason == "LOCATION_INSUFFICIENT_EVIDENCE"


def test_coordinate_bounding_box_validation():
    """Coordinate check: Coordinates outside UK boundary must be rejected."""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
    )

    # Coordinates in the Pacific Ocean (0.0, 0.0)
    candidate_ocean = NormalizedLeadRecord(
        source="google_maps",
        source_id="place_ocean",
        business_name="Oceanic Auto",
        address="Manchester, UK",
        latitude=0.0,
        longitude=0.0,
    )
    res = LocationValidator.evaluate_candidate(candidate_ocean, scope)
    assert res.is_valid is False
    assert res.rejection_reason == "LOCATION_COORDINATES_OUTSIDE_BOUNDARY"


def test_google_maps_structured_parsing():
    """Google Places API (New) structured addressComponents and coordinates extraction."""
    connector = GoogleMapsConnector(api_key="mock_key")
    raw_payload = {
        "id": "places/ChIJ27x_example",
        "displayName": {"text": "Manchester Precision Auto"},
        "formattedAddress": "100 Oxford Rd, Manchester M13 9PL, UK",
        "location": {"latitude": 53.468, "longitude": -2.232},
        "addressComponents": [
            {"longText": "100", "types": ["street_number"]},
            {"longText": "Oxford Road", "types": ["route"]},
            {"longText": "Manchester", "types": ["locality"]},
            {"longText": "Greater Manchester", "types": ["administrative_area_level_2"]},
            {"longText": "England", "types": ["administrative_area_level_1"]},
            {"longText": "United Kingdom", "shortText": "GB", "types": ["country"]},
            {"longText": "M13 9PL", "shortText": "M13 9PL", "types": ["postal_code"]},
        ],
        "nationalPhoneNumber": "0161 275 2000",
        "websiteUri": "https://manchesterauto.co.uk",
    }

    record = connector.parse_place_record(raw_payload)
    assert record.business_name == "Manchester Precision Auto"
    assert record.city == "Manchester"
    assert record.state == "England"
    assert record.country == "United Kingdom"
    assert record.country_code == "GB"
    assert record.postal_code == "M13 9PL"
    assert record.latitude == 53.468
    assert record.longitude == -2.232


def test_cross_country_deduplication_isolation():
    """Ensure two businesses with identical names in different countries are NOT falsely deduplicated."""
    engine = CanonicalIdentityEngine()

    cand = CanonicalLead(
        id="can_123",
        business_name="Precision Auto Body",
        city="Manchester",
        state="England",
        country="United Kingdom",
    )

    raw_us = RawLead(
        source_name="google_maps",
        source_record_id="us_456",
        business_name="Precision Auto Body",
        industry="Auto Repair",
        city="Manchester",
        state="Connecticut",
        country="United States",
    )

    match_explanation = engine.evaluate_candidate_match(raw_us, cand)
    assert match_explanation.match_level.value == "NO_MATCH"
    assert "Country mismatch" in match_explanation.reason


def test_salford_carfix_and_mcr_repairs_rejected_in_exact_city():
    """Salford businesses (Carfix and Manchester Car Repairs Ltd) must be rejected under EXACT_CITY."""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
        location_scope="EXACT_CITY",
    )

    carfix = NormalizedLeadRecord(
        source="google_maps",
        source_id="s1",
        business_name="Carfix Manchester",
        address="Unit 2 Bizcentres, 91-97 Liverpool St., Salford M5 4LG, UK",
        latitude=53.4812,
        longitude=-2.2689,
        city="Salford",
    )
    res_carfix = LocationValidator.evaluate_candidate(carfix, scope)
    assert res_carfix.is_valid is False
    assert res_carfix.rejection_reason == "LOCATION_CITY_BOUNDARY_MISMATCH"

    mcr_repairs = NormalizedLeadRecord(
        source="google_maps",
        source_id="s2",
        business_name="Manchester Car Repairs Ltd",
        address="263 Bury New Rd, Salford, Manchester M8 8DY, UK",
        latitude=53.4983,
        longitude=-2.2541,
        city="Salford",
    )
    res_mcr = LocationValidator.evaluate_candidate(mcr_repairs, scope)
    assert res_mcr.is_valid is False
    assert res_mcr.rejection_reason == "LOCATION_CITY_BOUNDARY_MISMATCH"


def test_wythenshawe_didsbury_cheetham_hill_accepted_in_exact_city():
    """Localities inside the City of Manchester local authority must be ACCEPTED under EXACT_CITY."""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
        location_scope="EXACT_CITY",
    )

    wythenshawe = NormalizedLeadRecord(
        source="google_maps",
        source_id="w1",
        business_name="Auto Doctor Manchester",
        address="124 Longley Ln, Sharston, Wythenshawe, Manchester M22 4SY, UK",
        latitude=53.3850,
        longitude=-2.2500,
        city="Wythenshawe",
    )
    res_w = LocationValidator.evaluate_candidate(wythenshawe, scope)
    assert res_w.is_valid is True
    assert res_w.rejection_reason is None

    didsbury = NormalizedLeadRecord(
        source="google_maps",
        source_id="d1",
        business_name="Didsbury Auto Care",
        address="750 Wilmslow Rd, Didsbury, Manchester M20 2DW, UK",
        latitude=53.4150,
        longitude=-2.2300,
        city="Didsbury",
    )
    res_d = LocationValidator.evaluate_candidate(didsbury, scope)
    assert res_d.is_valid is True

    cheetham = NormalizedLeadRecord(
        source="google_maps",
        source_id="c1",
        business_name="Cheetham Hill Garage",
        address="Broughton St, Cheetham Hill, Manchester M8 8NN, UK",
        latitude=53.5000,
        longitude=-2.2400,
        city="Cheetham Hill",
    )
    res_c = LocationValidator.evaluate_candidate(cheetham, scope)
    assert res_c.is_valid is True


def test_stretford_and_failsworth_rejected_in_exact_city():
    """Boroughs outside City of Manchester (Trafford/Oldham) must be rejected under EXACT_CITY."""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
        location_scope="EXACT_CITY",
    )

    stretford = NormalizedLeadRecord(
        source="google_maps",
        source_id="st1",
        business_name="Auto Crash Repair MCr Ltd",
        address="23 Talbot Rd, Old Trafford, Stretford, Manchester M16 0PE, UK",
        latitude=53.4589,
        longitude=-2.2845,
        city="Stretford",
    )
    res_st = LocationValidator.evaluate_candidate(stretford, scope)
    assert res_st.is_valid is False
    assert res_st.rejection_reason == "LOCATION_CITY_BOUNDARY_MISMATCH"

    failsworth = NormalizedLeadRecord(
        source="google_maps",
        source_id="f1",
        business_name="Mallu Mechanics",
        address="Morton St, Failsworth, Manchester M35 0BN, UK",
        latitude=53.5045,
        longitude=-2.1554,
        city="Failsworth",
    )
    res_f = LocationValidator.evaluate_candidate(failsworth, scope)
    assert res_f.is_valid is False
    assert res_f.rejection_reason == "LOCATION_CITY_BOUNDARY_MISMATCH"


def test_metro_area_mode_accepts_greater_manchester_boroughs():
    """Under METRO_AREA scope, Greater Manchester boroughs (Salford, Trafford, Oldham) are ACCEPTED."""
    _, _, scope = LocationValidator.validate_requested_configuration(
        country="United Kingdom",
        region="England",
        city="Manchester",
        location_scope="METRO_AREA",
    )

    salford = NormalizedLeadRecord(
        source="google_maps",
        source_id="s1",
        business_name="Carfix Manchester",
        address="Unit 2 Bizcentres, 91-97 Liverpool St., Salford M5 4LG, UK",
        latitude=53.4812,
        longitude=-2.2689,
        city="Salford",
    )
    res_s = LocationValidator.evaluate_candidate(salford, scope)
    assert res_s.is_valid is True

    stretford = NormalizedLeadRecord(
        source="google_maps",
        source_id="st1",
        business_name="Auto Crash Repair MCr Ltd",
        address="23 Talbot Rd, Old Trafford, Stretford, Manchester M16 0PE, UK",
        latitude=53.4589,
        longitude=-2.2845,
        city="Stretford",
    )
    res_st = LocationValidator.evaluate_candidate(stretford, scope)
    assert res_st.is_valid is True
