# mirror
https://calendar.google.com/calendar/ical/mutkcai83gusm8ek7o6nj00cr4%40group.calendar.google.com/public/basic.ics
holidays
https://calendar.google.com/calendar/ical/en.usa%23holiday%40group.v.calendar.google.com/public/basic.ics

```
/* default/calendar module configuration */
{
  module: "calendar",
  position: "top_left",
  config: {
    broadcastPastEvents: true, // <= IMPORTANT to see past events
    calendars: [
      {
        url: "webcal://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics",
        name: "us_holiday", // <= RECOMMENDED to assign name
        color: "red" // <= RECOMMENDED to assign color
      },
```
