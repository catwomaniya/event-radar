from datetime import datetime

from pydantic import BaseModel


class LumaGuest(BaseModel):
    name: str
    avatar_url: str | None = None
    x_handle: str | None = None
    x_profile_url: str | None = None
    luma_profile_url: str | None = None


class XProfile(BaseModel):
    handle: str
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    followers: str | None = None
    following: str | None = None
    error: str | None = None


class GuestRow(BaseModel):
    name: str
    x_handle: str | None = None
    x_bio: str | None = None
    x_location: str | None = None
    x_website: str | None = None
    x_followers: str | None = None
    luma_profile_url: str | None = None
    scrape_status: str = "pending"
    scraped_at: str | None = None

    @classmethod
    def from_guest_and_profile(
        cls, guest: LumaGuest, profile: XProfile | None = None
    ) -> "GuestRow":
        row = cls(
            name=guest.name,
            x_handle=guest.x_handle,
            luma_profile_url=guest.luma_profile_url,
        )
        if profile is None:
            if guest.x_handle:
                row.scrape_status = "x_skipped"
            else:
                row.scrape_status = "no_x_handle"
        elif profile.error:
            row.scrape_status = f"x_error: {profile.error}"
        else:
            row.x_bio = profile.bio
            row.x_location = profile.location
            row.x_website = profile.website
            row.x_followers = profile.followers
            row.scrape_status = "ok"
        row.scraped_at = datetime.now().isoformat(timespec="seconds")
        return row

    @staticmethod
    def header() -> list[str]:
        return [
            "Name",
            "X Handle",
            "X Bio",
            "X Location",
            "X Website",
            "X Followers",
            "Luma Profile",
            "Scrape Status",
            "Scraped At",
        ]

    def to_row(self) -> list[str]:
        return [
            self.name,
            self.x_handle or "",
            self.x_bio or "",
            self.x_location or "",
            self.x_website or "",
            self.x_followers or "",
            self.luma_profile_url or "",
            self.scrape_status,
            self.scraped_at or "",
        ]
