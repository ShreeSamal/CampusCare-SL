
from pydantic import BaseModel, Field, model_validator


class CreateIssueRequest(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=0, max_length=5000)
    building_id: str | None = Field(default=None, max_length=100)
    room: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_text: str | None = Field(default=None, max_length=300)
    photo_urls: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        return self


class IssueListQuery(BaseModel):
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
