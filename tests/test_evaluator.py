import pytest

from app.evaluator import evaluate
from app.models import ChecklistRequest


def test_generic_baseline():
	req = ChecklistRequest(
		state="US",
		property_type="single_family",
		bedrooms=2,
		floors=1,
		has_fuel_appliance=False,
		has_attached_garage=False,
	)
	plan = evaluate(req)
	# Expect smoke placements (bedrooms, outside sleeping, each level) and no CO
	smoke_places = {r.place for r in plan.recommendations if r.type == "smoke"}
	assert {"each_bedroom", "outside_sleeping_areas", "each_level_incl_basement"}.issubset(smoke_places)
	assert not any(r.type == "co" for r in plan.recommendations)


def test_co_condition():
	req = ChecklistRequest(
		state="US",
		property_type="single_family",
		bedrooms=2,
		floors=1,
		has_fuel_appliance=True,
		has_attached_garage=False,
	)
	plan = evaluate(req)
	assert any(r.type == "co" for r in plan.recommendations)
	co_places = {r.place for r in plan.recommendations if r.type == "co"}
	assert "near_sleeping_areas" in co_places or "outside_sleeping_areas" in co_places


def test_state_overlay():
	req = ChecklistRequest(
		state="CA",
		property_type="single_family",
		bedrooms=2,
		floors=1,
		has_fuel_appliance=False,
		has_attached_garage=False,
		permit_planned=True,
	)
	plan = evaluate(req)
	assert any("california" in (r.citation or "").lower() for r in plan.recommendations) or any("ca:" in n.lower() for n in plan.notes)
	assert "US/CA/common" in plan.jurisdiction_chain


def test_permit_note():
	req = ChecklistRequest(
		state="US",
		property_type="single_family",
		bedrooms=2,
		floors=1,
		has_fuel_appliance=False,
		has_attached_garage=False,
		permit_planned=True,
	)
	plan = evaluate(req)
	assert any("hardwired" in n.lower() or "interconnect" in n.lower() for n in plan.notes)


