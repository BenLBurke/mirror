# mirror
https://calendar.google.com/calendar/ical/mutkcai83gusm8ek7o6nj00cr4%40group.calendar.google.com/public/basic.ics
holidays
https://calendar.google.com/calendar/ical/en.usa%23holiday%40group.v.calendar.google.com/public/basic.ics

```
{
  module: "MMM-CalendarExt3",
  position: "top_center",
  config: {
    locale: "en-US",
    debug: true,
    calendars: [
      {
        name: "US Holidays",
        url: "https://calendar.google.com/calendar/ical/en.usa%23holiday%40group.v.calendar.google.com/public/basic.ics"
      }
    ],
    views: [
      {
        name: "simple",
        mode: "upcoming",
        type: "column",
        slotCount: 10
      }
    ],
    scenes: [
      {
        name: "default",
        views: ["simple"]
      }
    ],
    defaultScene: "default"
  }
}
```
