"""A calendar of what Holiday Lighting will show each night."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HolidayLightingConfigEntry
from .const import MODE_CYCLE, MODE_FADE, MODE_ROTATE, MODE_STATIC, MODE_TWINKLE
from .controller import Holiday, HolidayLightingController
from .entity import HolidayLightingEntity
from .schedule import night_of

# The frontend asks for a month or so at a time; cap anything larger.
MAX_RANGE = timedelta(days=800)

EFFECT_NAMES = {
    MODE_ROTATE: "Chase",
    MODE_STATIC: "Static",
    MODE_CYCLE: "Whole-house cycle",
    MODE_FADE: "Whole-house fade",
    MODE_TWINKLE: "Twinkle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HolidayLightingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the schedule calendar."""
    async_add_entities([HolidayScheduleCalendar(entry.runtime_data, "schedule")])


def _description(
    controller: HolidayLightingController, holiday: Holiday, day: date
) -> str:
    lines = [f"Colors: {', '.join(holiday.color_names)}"]
    effect = EFFECT_NAMES.get(holiday.mode, holiday.mode)
    if holiday.mode != MODE_STATIC and len(holiday.colors) > 1:
        effect += f", every {holiday.interval}s"
    lines.append(f"Effect: {effect}")
    if controller.use_schedule:
        off_time = controller.off_time_for(holiday, day)
        if off_time is not None:
            lines.append(f"Off at {off_time.strftime('%-I:%M %p')}")
        elif holiday.all_night or controller.duration_for(holiday) is None:
            lines.append("On until it gets light")
    lines.append(f"Lights: {len(holiday.lights)}")
    return "\n".join(lines)


class HolidayScheduleCalendar(HolidayLightingEntity, CalendarEntity):
    """One all-day event per run of nights showing the same holiday."""

    def _events(self, first: date, last: date) -> list[CalendarEvent]:
        """Events covering nights first..last (inclusive)."""
        controller = self.controller
        events: list[CalendarEvent] = []
        run: tuple[Holiday, date, date] | None = None

        def close() -> None:
            if run is None:
                return
            holiday, start, end = run
            events.append(
                CalendarEvent(
                    start=start,
                    end=end + timedelta(days=1),  # all-day end is exclusive
                    summary=holiday.name,
                    description=_description(controller, holiday, start),
                    uid=f"{holiday.id}-{start.isoformat()}",
                )
            )

        day = first
        while day <= last:
            holiday = controller.planned_for(day)
            if run is not None and holiday is not None and run[0].id == holiday.id:
                run = (run[0], run[1], day)
            else:
                close()
                run = (holiday, day, day) if holiday is not None else None
            day += timedelta(days=1)
        close()
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Tonight's event, or the next one coming up."""
        tonight = night_of(dt_util.now())
        for event in self._events(tonight, tonight + timedelta(days=400)):
            return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Events between two times."""
        first = dt_util.as_local(start_date).date()
        last = dt_util.as_local(end_date).date()
        if dt_util.as_local(end_date).time() == datetime.min.time() and last > first:
            last -= timedelta(days=1)  # an exclusive midnight end
        last = min(last, first + MAX_RANGE)
        events = self._events(first, last)
        # Include a run that started before the range but overlaps it.
        if events and events[0].start == first:
            holiday = self.controller.planned_for(first)
            start = first
            while (
                holiday is not None
                and (prev := self.controller.planned_for(start - timedelta(days=1)))
                is not None
                and prev.id == holiday.id
                and first - start < timedelta(days=60)
            ):
                start -= timedelta(days=1)
            if start != first:
                events[0] = CalendarEvent(
                    start=start,
                    end=events[0].end,
                    summary=events[0].summary,
                    description=events[0].description,
                    uid=f"{holiday.id}-{start.isoformat()}",
                )
        return events
