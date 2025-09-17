import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
	ChecklistRequest,
	ChecklistResponse,
	ChecklistPlan,
	Recommendation,
	TestingAction,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "rules"


def _load_json(path: Path) -> Dict[str, Any]:
	with path.open("r", encoding="utf-8") as f:
		return json.load(f)


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
	"""Recursively merge overlay into base. Lists are concatenated; scalars are overridden."""
	result: Dict[str, Any] = {**base}
	for key, overlay_value in overlay.items():
		if key in result:
			base_value = result[key]
			if isinstance(base_value, dict) and isinstance(overlay_value, dict):
				result[key] = _deep_merge(base_value, overlay_value)
			elif isinstance(base_value, list) and isinstance(overlay_value, list):
				result[key] = base_value + overlay_value
			else:
				result[key] = overlay_value
		else:
			result[key] = overlay_value
	return result


def _normalize_state_parts(state: str) -> (str, Optional[str]):
	"""Return (country, region) where region may be None. Accepts 'US', 'CA', 'US-CA'."""
	s = state.strip()
	if "-" in s:
		parts = s.split("-")
		return parts[0].upper(), parts[-1].upper()
	if len(s) == 2:
		return "US", s.upper()
	return s.upper(), None


_STATE_NAME_TO_ABBR = {
	"california": "CA",
	"ca": "CA",
	"new york": "NY",
	"ny": "NY",
	"texas": "TX",
	"tx": "TX",
	"florida": "FL",
	"fl": "FL",
}


def _normalize_state_input(state_code: Optional[str]) -> Optional[str]:
	if not state_code:
		return None
	s = state_code.strip()
	if not s:
		return None
	if "-" in s:
		# US-CA → CA
		parts = s.split("-")
		return parts[-1].upper()
	key = s.lower()
	return _STATE_NAME_TO_ABBR.get(key, s.upper() if len(s) == 2 else None)


def _jurisdiction_to_path(j: str) -> Path:
	# "US/common" → rules/US/common.json | "US/CA/common" → rules/US/CA/common.json
	parts = j.split("/")
	return RULES_DIR.joinpath(*parts).with_suffix(".json")


def load_rules_chain(state_code: Optional[str]) -> Tuple[List[str], Dict[str, Any]]:
	"""Return jurisdiction chain and merged ruleset (base with overlay)."""
	chain: List[str] = ["US/common"]
	base = _load_json(_jurisdiction_to_path("US/common"))
	merged = dict(base)
	state_abbr = _normalize_state_input(state_code)
	if state_abbr:
		state_path = RULES_DIR / "US" / state_abbr / "common.json"
		if state_path.exists():
			chain.append(f"US/{state_abbr}/common")
			merged = _deep_merge(merged, _load_json(state_path))
	return chain, merged


def load_rules_for_state(state: str) -> Dict[str, Any]:
	"""Load base US rules and optional state overlay if present."""
	country, region = _normalize_state_parts(state)
	base_path = RULES_DIR / "US" / "common.json"
	if not base_path.exists():
		raise FileNotFoundError(f"Base rules not found at {base_path}")
	merged = _load_json(base_path)
	if country == "US" and region:
		overlay_path = RULES_DIR / "US" / region / "common.json"
		if overlay_path.exists():
			overlay = _load_json(overlay_path)
			merged = _deep_merge(merged, overlay)
	return merged


def _get_input_value(inputs: Dict[str, Any], field: str) -> Any:
	return inputs.get(field)


def _match_leaf_condition(cond: Dict[str, Any], inputs: Dict[str, Any]) -> bool:
	field = cond.get("field")
	if not field:
		return True
	value = _get_input_value(inputs, field)
	if "eq" in cond:
		return value == cond["eq"]
	if "ne" in cond:
		return value != cond["ne"]
	if "in" in cond:
		return value in cond["in"]
	if "nin" in cond:
		return value not in cond["nin"]
	if "gt" in cond:
		if value is None:
			return False
		return value > cond["gt"]
	if "gte" in cond:
		if value is None:
			return False
		return value >= cond["gte"]
	if "lt" in cond:
		if value is None:
			return False
		return value < cond["lt"]
	if "lte" in cond:
		if value is None:
			return False
		return value <= cond["lte"]
	return True


def _match_condition(condition: Optional[Dict[str, Any]], inputs: Dict[str, Any]) -> bool:
	if not condition:
		return True
	if "all" in condition:
		return all(_match_condition(c, inputs) for c in condition["all"])
	if "any" in condition:
		return any(_match_condition(c, inputs) for c in condition["any"])
	if "not" in condition:
		return not _match_condition(condition["not"], inputs)
	return _match_leaf_condition(condition, inputs)


def _match_when_new_schema(condition: Optional[Dict[str, Any]], inputs: Dict[str, Any]) -> bool:
	"""Matcher for compact schema 'when'. Supports: always, all, any, not, eq(map)."""
	if not condition:
		return True
	if isinstance(condition, bool):
		return bool(condition)
	if "always" in condition:
		return bool(condition.get("always"))
	if "all" in condition:
		return all(_match_when_new_schema(c, inputs) for c in condition["all"])
	if "any" in condition:
		return any(_match_when_new_schema(c, inputs) for c in condition["any"])
	if "not" in condition:
		return not _match_when_new_schema(condition["not"], inputs)
	if "eq" in condition:
		m = condition["eq"] or {}
		for k, v in m.items():
			if inputs.get(k) != v:
				return False
		return True
	# Optional simple operators: {"gte": {"floors": 2}} etc.
	for op in ("gte", "gt", "lte", "lt"):
		if op in condition:
			m = condition[op] or {}
			for k, v in m.items():
				val = inputs.get(k)
				if val is None:
					return False
				if op == "gte" and not (val >= v):
					return False
				if op == "gt" and not (val > v):
					return False
				if op == "lte" and not (val <= v):
					return False
				if op == "lt" and not (val < v):
					return False
			return True
	# Fallback to old leaf style if given
	return _match_leaf_condition(condition, inputs)


def _evaluate_section(section_rules: List[Dict[str, Any]], inputs: Dict[str, Any]) -> List[str]:
	results: List[str] = []
	for rule in section_rules:
		when = rule.get("when")
		if _match_condition(when, inputs):
			text = rule.get("text")
			if text:
				results.append(text)
	return results


def evaluate_checklist(req: ChecklistRequest) -> ChecklistResponse:
	merged_rules = load_rules_for_state(req.state)
	inputs: Dict[str, Any] = {
		"state": req.state,
		"property_type": str(req.property_type),
		"bedrooms": req.bedrooms,
		"floors": req.floors,
		"has_fuel_garage": bool(getattr(req, "has_fuel_appliance", False) or getattr(req, "has_attached_garage", False)),
		"has_fuel_appliance": getattr(req, "has_fuel_appliance", False),
		"has_attached_garage": getattr(req, "has_attached_garage", False),
		"year_bucket": str(req.year_bucket) if getattr(req, "year_bucket", None) is not None else None,
		"interconnect_present": str(req.interconnect_present) if getattr(req, "interconnect_present", None) is not None else None,
		"permit_planned": req.permit_planned,
	}

	# New compact schema path
	if "rules" in merged_rules:
		smoke: List[str] = []
		co: List[str] = []
		devices: List[str] = []
		notes: List[str] = []
		citations_set = set()
		# Sort rules by priority desc then stable index
		rules_list = list(merged_rules.get("rules", []))
		rules_list.sort(key=lambda r: int(r.get("priority", 0)), reverse=True)

		place_phrase = {
			"each_bedroom": "inside every bedroom.",
			"outside_sleeping_areas": "outside each sleeping area.",
			"each_level_incl_basement": "on every level, including basements.",
			"near_sleeping_areas": "near sleeping areas.",
			"common_hallways": "in common hallways.",
			"other": "as noted.",
		}

		for rule in rules_list:
			when = rule.get("when")
			if not _match_when_new_schema(when, inputs):
				continue
			for rec in rule.get("recommend", []) or []:
				rec_type = rec.get("type")
				place = rec.get("place")
				note = rec.get("note")
				citation = rec.get("citation")
				if citation:
					citations_set.add(str(citation))
				phrase = place_phrase.get(str(place), "as noted.")
				if rec_type == "co":
					text = f"Install CO alarm {phrase}"
				elif rec_type == "smoke":
					text = f"Install smoke alarm {phrase}"
				else:
					text = f"Install {phrase}"
				if note:
					text = f"{text} {note}".strip()
				if rec_type == "smoke":
					if text not in smoke:
						smoke.append(text)
				elif rec_type == "co":
					if text not in co:
						co.append(text)
				else:
					if text not in devices:
						devices.append(text)
			for n in rule.get("notes", []) or []:
				if n not in notes:
					notes.append(n)

		# testing block
		testing_entries: List[str] = []
		for t in merged_rules.get("testing", []) or []:
			action = str(t.get("action", "")).strip()
			freq = str(t.get("frequency", "")).strip()
			note = t.get("note")
			if not action or not freq:
				continue
			phrase = {
				"test": "Test",
				"clean": "Clean",
				"replace_battery": "Replace battery",
				"replace_device": "Replace device",
			}.get(action, action.capitalize())
			when_text = {
				"monthly": "monthly",
				"quarterly": "quarterly",
				"annual": "annually",
				"10_years": "every 10 years",
				"per_manufacturer": "per manufacturer",
			}.get(freq, freq)
			line = f"{phrase} {when_text}."
			if note:
				line = f"{line} {note}".strip()
			if line not in testing_entries:
				testing_entries.append(line)

		return ChecklistResponse(
			smoke=smoke,
			co=co,
			devices=devices,
			testing=testing_entries,
			notes=notes,
			citations=sorted(citations_set),
		)

	# Legacy schema path
	def section(name: str) -> List[Dict[str, Any]]:
		return list(merged_rules.get(name, []))

	return ChecklistResponse(
		smoke=_evaluate_section(section("smoke"), inputs),
		co=_evaluate_section(section("co"), inputs),
		devices=_evaluate_section(section("devices"), inputs),
		testing=_evaluate_section(section("testing"), inputs),
		notes=_evaluate_section(section("notes"), inputs),
		citations=_evaluate_section(section("citations"), inputs),
	)


def evaluate(plan_request: ChecklistRequest) -> ChecklistPlan:
	"""Evaluate compact schema into a structured ChecklistPlan."""
	chain, _ = load_rules_chain(plan_request.state)
	inputs: Dict[str, Any] = {
		"state": plan_request.state,
		"property_type": str(plan_request.property_type),
		"bedrooms": plan_request.bedrooms,
		"floors": plan_request.floors,
		"has_fuel_appliance": getattr(plan_request, "has_fuel_appliance", False),
		"has_attached_garage": getattr(plan_request, "has_attached_garage", False),
		"year_bucket": str(plan_request.year_bucket) if getattr(plan_request, "year_bucket", None) is not None else None,
		"interconnect_present": str(plan_request.interconnect_present) if getattr(plan_request, "interconnect_present", None) is not None else None,
		"permit_planned": plan_request.permit_planned,
	}

	# Helper to know specificity: later in chain is more specific
	def specificity_index(j: str) -> int:
		return chain.index(j)

	# Aggregate recommendations and notes
	rec_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
	plan_notes: List[str] = []

	# Process jurisdiction in order
	for j in chain:
		doc = _load_json(_jurisdiction_to_path(j))
		priority_sorted = sorted(doc.get("rules", []), key=lambda r: int(r.get("priority", 0)), reverse=True)
		for rule in priority_sorted:
			if not _match_when_new_schema(rule.get("when"), inputs):
				continue
			for rec in rule.get("recommend", []) or []:
				key = (str(rec.get("type")), str(rec.get("place")))
				new_item = {
					"type": key[0],
					"place": key[1],
					"notes": [rec.get("note")] if rec.get("note") else [],
					"citations": set([str(rec.get("citation"))]) if rec.get("citation") else set(),
					"source": rec.get("source") or j,
					"confidence": rec.get("confidence"),
					"priority": int(rule.get("priority", 0)),
					"jurisdiction": j,
				}
				existing = rec_by_key.get(key)
				if not existing:
					rec_by_key[key] = new_item
					continue
				# Resolve conflicts: prefer higher priority; if tie, more specific jurisdiction
				better = False
				if new_item["priority"] > existing["priority"]:
					better = True
				elif new_item["priority"] == existing["priority"] and specificity_index(j) > specificity_index(existing["jurisdiction"]):
					better = True
				if better:
					# Keep union of notes/citations
					new_item["notes"] = list({*existing["notes"], *new_item["notes"]})
					new_item["citations"] = set(existing["citations"]) | set(new_item["citations"])
					rec_by_key[key] = new_item
				else:
					# Merge notes/citations into existing
					existing["notes"] = list({*existing["notes"], *new_item["notes"]})
					existing["citations"] |= set(new_item["citations"])  # type: ignore
			for n in rule.get("notes", []) or []:
				if n not in plan_notes:
					plan_notes.append(n)

	# Build recommendations list
	recommendations: List[Recommendation] = []
	for item in rec_by_key.values():
		recommendations.append(
			Recommendation(
				type=item["type"],
				place=item["place"],
				note="; ".join(item["notes"]) if item["notes"] else None,
				source=item.get("source") or item.get("jurisdiction"),
				citation=", ".join(sorted(item["citations"])) if item["citations"] else None,
				confidence=item.get("confidence"),
			)
		)

	# Testing: start with most specific, then append unique from less specific
	testing_seen: set[Tuple[str, str]] = set()
	testing_actions: List[TestingAction] = []
	for j in reversed(chain):  # most specific first
		doc = _load_json(_jurisdiction_to_path(j))
		for t in doc.get("testing", []) or []:
			key = (str(t.get("action")), str(t.get("frequency")))
			if key in testing_seen:
				continue
			testing_seen.add(key)
			testing_actions.append(
				TestingAction(
					action=str(t.get("action")),
					frequency=str(t.get("frequency")),
					note=t.get("note"),
					citation=t.get("citation"),
				)
			)

	# Reverse to keep most specific first as appended; optional
	testing_actions = list(testing_actions)

	return ChecklistPlan(
		recommendations=recommendations,
		testing=testing_actions,
		notes=plan_notes,
		jurisdiction_chain=chain,
	)


