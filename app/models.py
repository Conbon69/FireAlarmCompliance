from datetime import date
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# Enums/Literals for constrained fields (serialize as strings)
class PropertyType(str, Enum):
	single_family = "single_family"
	duplex = "duplex"
	apartment = "apartment"


class YearBucket(str, Enum):
	lt_1999 = "lt_1999"
	y1999_2010 = "y1999_2010"
	y2011_plus = "y2011_plus"


class InterconnectPresence(str, Enum):
	yes = "yes"
	no = "no"
	unknown = "unknown"


class RecommendationType(str, Enum):
	smoke = "smoke"
	co = "co"


class PlaceType(str, Enum):
	each_bedroom = "each_bedroom"
	outside_sleeping_areas = "outside_sleeping_areas"
	each_level_incl_basement = "each_level_incl_basement"
	near_sleeping_areas = "near_sleeping_areas"
	common_hallways = "common_hallways"
	other = "other"


class TestingActionType(str, Enum):
	test = "test"
	clean = "clean"
	replace_battery = "replace_battery"
	replace_device = "replace_device"


class TestingFrequency(str, Enum):
	monthly = "monthly"
	quarterly = "quarterly"
	annual = "annual"
	ten_years = "10_years"
	per_manufacturer = "per_manufacturer"


class ChecklistRequest(BaseModel):
	# Location / type
	state: str = Field(..., description="US 2-letter or full string, e.g., 'US-CA' or 'US'")
	property_type: PropertyType

	# Facts
	bedrooms: int = Field(..., ge=0)
	floors: int = Field(..., ge=1)
	has_fuel_appliance: bool
	has_attached_garage: bool
	year_bucket: Optional[YearBucket] = None
	interconnect_present: InterconnectPresence = InterconnectPresence.unknown
	permit_planned: bool = False

	# Back-compat for current evaluator: derive combined flag
	# Not part of the requested schema, but maintained to avoid breaking callers.
	has_fuel_garage: Optional[bool] = Field(
		None,
		description="Derived: fuel appliance or attached garage present (compat)",
	)

	@model_validator(mode="after")
	def _compute_compat_fields(self) -> "ChecklistRequest":
		if self.has_fuel_garage is None:
			self.has_fuel_garage = bool(self.has_fuel_appliance or self.has_attached_garage)
		return self


class Recommendation(BaseModel):
	type: RecommendationType
	place: PlaceType
	note: Optional[str] = None
	source: Optional[str] = Field(None, description="e.g., model_code | state | city")
	citation: Optional[str] = None
	confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class TestingAction(BaseModel):
	action: TestingActionType
	frequency: TestingFrequency
	note: Optional[str] = None
	citation: Optional[str] = None


class ChecklistPlan(BaseModel):
	recommendations: List[Recommendation] = []
	testing: List[TestingAction] = []
	notes: List[str] = []
	jurisdiction_chain: List[str] = []
	# Optional: authoritative links per jurisdiction
	resources: List[dict] = []


class ICSRequest(BaseModel):
	email: Optional[str] = None
	frequency: Literal["monthly"] = "monthly"
	months: int = 12
	start_date: Optional[date] = None
	title: str = "Test smoke/CO alarms"
	description: str = "Monthly test reminder"


# Legacy response kept for MVP endpoints
class ChecklistResponse(BaseModel):
	smoke: List[str] = []
	co: List[str] = []
	devices: List[str] = []
	testing: List[str] = []
	notes: List[str] = []
	citations: List[str] = []


