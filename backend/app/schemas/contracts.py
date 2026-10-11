from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserCreate(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)
    password: str = Field(min_length=12, max_length=200)


class UserPatch(Input):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=200)


class StudentCreate(Input):
    name: str = Field(min_length=2, max_length=120)
    erp_id: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    email: str = Field(
        default="", max_length=254, pattern=r"^$|^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    department: str = Field(min_length=1, max_length=100)
    program: str = Field(min_length=1, max_length=100)
    semester: int = Field(ge=1, le=20)
    section: str = Field(min_length=1, max_length=20)
    active: bool = True
    consent: bool = False


class StudentPatch(Input):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    erp_id: str | None = Field(
        default=None, min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$"
    )
    email: str | None = Field(
        default=None, max_length=254, pattern=r"^$|^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    department: str | None = Field(default=None, min_length=1, max_length=100)
    program: str | None = Field(default=None, min_length=1, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=20)
    section: str | None = Field(default=None, min_length=1, max_length=20)
    active: bool | None = None
    consent: bool | None = None


class CourseCreate(Input):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    department: str = Field(min_length=1, max_length=100)
    semester: int = Field(ge=1, le=20)
    section: str = Field(min_length=1, max_length=20)
    academic_year: str = Field(min_length=4, max_length=20)
    active: bool = True


class CoursePatch(Input):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    active: bool | None = None


class Enrollment(Input):
    student_ids: list[str] = Field(min_length=1, max_length=200)


class Assignment(Input):
    course_id: str
    faculty_id: str


class SessionCreate(Input):
    course_id: str
    faculty_id: str
    starts_at: datetime
    ends_at: datetime
    room: str = Field(min_length=1, max_length=80)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc(cls, v):
        if v.tzinfo is None:
            raise ValueError("Timezone offset required")
        return v.astimezone(timezone.utc).replace(tzinfo=None)

    @model_validator(mode="after")
    def order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("End time must follow start time")
        return self


class Correction(Input):
    status: Literal["PRESENT", "LATE", "ABSENT", "EXCUSED", "REVIEW"]
    reason: str = Field(min_length=5, max_length=500)


class Manual(Correction):
    student_id: str


class Policy(Input):
    late_grace_minutes: int = Field(default=10, ge=0, le=120)
    recognition_threshold: float = Field(default=0.55, ge=0.1, le=0.99)
    ambiguity_margin: float = Field(default=0.08, ge=0.01, le=0.5)
    smoothing_frames: int = Field(default=3, ge=2, le=10)
    faculty_corrections: bool = False
    liveness_required: bool = False
    event_retention_days: int = Field(default=30, ge=1, le=365)
    biometric_retention_days: int = Field(default=365, ge=1, le=3650)
    excused_in_denominator: bool = False
    late_counts_present: bool = True
    calibration_approved: bool = False
    calibration_note: str = Field(default="", max_length=500)
