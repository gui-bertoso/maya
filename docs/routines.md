# Personal routines

`RoutineManager` maintains daily plans in `data/routine.json`.

## Presets

- Routine A: a 06:00 workout with work/study blocks throughout the day.
- Routine B: a 14:00 workout with a morning adjusted for work and rest.

Activities can be pending, in progress, completed or skipped. Completion awards
XP only once; streaks count days with actual progress.

## Adaptation

`!awake HH:MM` shifts flexible blocks after a late start while preserving fixed
appointments. Current priority: fixed appointments, work, Rust, English,
international planning and leisure.

## Persistence

The file stores a schema version, active routine, recorded days and preferences.
Future changes must include an explicit migration and must never silently erase history.

## Reminders

The runtime checks reminders once per minute and records delivered reminders to
avoid duplicates. Future quiet hours should suppress interruptions without losing
pending events.
