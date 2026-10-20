from helpers.diagnostics import report_error
import json
import re
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

from helpers.config import get_path


DEFAULT_ROUTINES = {
    "a": [
        ("wake", "Acordar", "05:30", "06:00", True, 0),
        ("gym", "Treino", "06:00", "07:30", True, 0),
        ("breakfast", "Cafe e banho", "07:30", "08:30", False, 1),
        ("work", "Trabalho", "08:30", "11:30", False, 2),
        ("lunch", "Almoco", "11:30", "12:30", False, 1),
        ("rust", "Rust", "12:30", "14:30", False, 3),
        ("english", "Ingles", "14:30", "15:30", False, 4),
        ("ireland", "Irlanda", "15:30", "16:30", False, 5),
        ("free", "Livre", "16:30", "17:30", False, 6),
        ("prepare", "Comer e preparar", "17:30", "18:20", True, 0),
        ("school", "Escola", "18:30", "23:00", True, 0),
    ],
    "b": [
        ("wake", "Acordar", "07:30", "08:00", True, 0),
        ("breakfast", "Cafe", "08:00", "08:30", False, 1),
        ("work", "Trabalho", "08:30", "11:30", False, 2),
        ("lunch", "Almoco", "11:30", "12:30", False, 1),
        ("rust", "Rust", "12:30", "13:30", False, 3),
        ("gym", "Treino", "14:00", "15:30", True, 0),
        ("recovery", "Banho e comer", "15:30", "16:00", False, 1),
        ("rust_2", "Rust", "16:00", "17:00", False, 3),
        ("english", "Ingles", "17:00", "17:45", False, 4),
        ("ireland", "Irlanda", "17:45", "18:20", False, 5),
        ("school", "Escola", "18:30", "23:00", True, 0),
    ],
}

ALIASES = {
    "academia": "gym", "treino": "gym", "gym": "gym",
    "trabalho": "work", "work": "work", "rust": "rust",
    "ingles": "english", "english": "english", "irlanda": "ireland",
    "ireland": "ireland", "escola": "school", "school": "school",
    "almoco": "lunch", "lunch": "lunch", "cafe": "breakfast",
}


class RoutineManager:
    """Owns routine scheduling, command parsing and local progress history."""

    def __init__(self, path=None, now_provider=None):
        self.path = Path(path or get_path("ROUTINE_PATH", "data/routine.json"))
        self.now_provider = now_provider or datetime.now
        self.data = self._load()

    @staticmethod
    def _defaults():
        return {"version": 1, "active_routine": "a", "days": {}, "settings": {"reminders": True}}

    def _load(self):
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                loaded = json.load(stream)
            result = self._defaults()
            result.update(loaded if isinstance(loaded, dict) else {})
            return result
        except (OSError, ValueError, TypeError) as error:
            if self.path.exists():
                report_error("routine_storage", error, operation="routine.load", notify=False)
            return self._defaults()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            with temp_path.open("w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2)
            temp_path.replace(self.path)
        except Exception as error:
            report_error("routine_storage", error, operation="routine.save")
            raise

    def _now(self, now=None):
        return now or self.now_provider()

    def _day(self, now=None):
        now = self._now(now)
        key = now.date().isoformat()
        day = self.data["days"].setdefault(key, {
            "routine": self.data["active_routine"], "awake_at": None,
            "tasks": {}, "notified": [],
        })
        return key, day

    @staticmethod
    def _minutes(value):
        hours, minutes = map(int, value.split(":"))
        return hours * 60 + minutes

    @staticmethod
    def _clock(value):
        value = max(0, min(value, 24 * 60 - 1))
        return f"{value // 60:02d}:{value % 60:02d}"

    @staticmethod
    def _task(entry):
        key, label, start, end, fixed, priority = entry
        return {"key": key, "label": label, "start": start, "end": end,
                "fixed": fixed, "priority": priority}

    def schedule(self, now=None):
        _, day = self._day(now)
        tasks = [self._task(item) for item in deepcopy(DEFAULT_ROUTINES[day["routine"]])]
        awake_at = day.get("awake_at")
        if not awake_at:
            return tasks

        awake = self._minutes(awake_at)
        first_start = self._minutes(tasks[0]["start"])
        if awake <= first_start:
            return tasks

        # Fixed commitments stay fixed. Flexible tasks are packed into the free
        # windows after wake-up; lower-priority items lose time first.
        fixed = [task for task in tasks if task["fixed"] and task["key"] != "wake"
                 and self._minutes(task["end"]) > awake]
        flexible = [task for task in tasks if not task["fixed"]]
        durations = {task["key"]: self._minutes(task["end"]) - self._minutes(task["start"]) for task in flexible}
        cursor = awake
        rebuilt = [{"key": "wake", "label": "Acordar", "start": awake_at,
                    "end": self._clock(awake + 15), "fixed": True, "priority": 0}]

        for task in sorted(flexible, key=lambda item: (item["priority"], self._minutes(item["start"]))):
            duration = durations[task["key"]]
            blockers = sorted([item for item in fixed if self._minutes(item["end"]) > cursor],
                              key=lambda item: self._minutes(item["start"]))
            while blockers and cursor >= self._minutes(blockers[0]["start"]):
                cursor = max(cursor, self._minutes(blockers.pop(0)["end"]))
            limit = self._minutes(blockers[0]["start"]) if blockers else 18 * 60 + 20
            available = max(0, limit - cursor)
            allocated = min(duration, available)
            if allocated >= 20:
                copy = dict(task)
                copy["start"], copy["end"] = self._clock(cursor), self._clock(cursor + allocated)
                rebuilt.append(copy)
                cursor += allocated

        rebuilt.extend(fixed)
        return sorted(rebuilt, key=lambda item: self._minutes(item["start"]))

    def _find_tasks(self, value, now=None):
        normalized = self._normalize(value)
        key = ALIASES.get(normalized, normalized)
        schedule = self.schedule(now)
        matches = [task for task in schedule if task["key"] == key]
        if key == "rust":
            matches += [task for task in schedule if task["key"] == "rust_2"]
        return matches

    @staticmethod
    def _normalize(value):
        import unicodedata
        value = unicodedata.normalize("NFKD", (value or "").lower())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9_]+", " ", value).strip()

    def handle_command(self, text, now=None):
        now = self._now(now)
        clean = self._normalize(text.lstrip("!"))
        if clean in {"today", "hoje", "minha rotina"}:
            return self.format_today(now)
        if clean in {"status", "progresso"}:
            return self.format_status(now)
        if clean in {"week", "semana"}:
            return self.format_week(now)
        match = re.fullmatch(r"routine\s+([ab])|rotina\s+([ab])", clean)
        if match:
            return self.set_routine(match.group(1) or match.group(2), now)
        match = re.fullmatch(r"(?:done|feito|conclui)\s+(.+)", clean)
        if match:
            return self.set_task_status(match.group(1), "done", now)
        match = re.fullmatch(r"(?:skip|pular|pulei)\s+(.+)", clean)
        if match:
            return self.set_task_status(match.group(1), "skipped", now)
        match = re.search(r"(?:awake|acordei)(?:\s+as)?\s+(\d{1,2})\s+(\d{2})", clean)
        if match:
            return self.recalculate(f"{int(match.group(1)):02d}:{match.group(2)}", now)
        return None

    def set_routine(self, routine, now=None):
        routine = routine.lower()
        self.data["active_routine"] = routine
        _, day = self._day(now)
        day["routine"] = routine
        day["notified"] = []
        self.save()
        return f"Rotina {routine.upper()} ativada. {('Treino as 06:00.' if routine == 'a' else 'Treino as 14:00 e mais sono. Sabia escolha 😴')}"

    def set_task_status(self, name, status, now=None):
        _, day = self._day(now)
        matches = self._find_tasks(name, now)
        if not matches:
            return f"Nao achei '{name}' na rotina de hoje. Usa !today pra ver os nomes."
        changed = 0
        for task in matches:
            if day["tasks"].get(task["key"]) != status:
                day["tasks"][task["key"]] = status
                changed += 1
        self.save()
        label = matches[0]["label"]
        if status == "done":
            return f"{label} concluido. +{changed * 100} XP. Maya viu, Maya contabilizou 😎"
        return f"{label} pulado sem drama. Amanhã a gente cobra a divida 👀"

    def recalculate(self, awake_at, now=None):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", awake_at):
            return "Horario invalido. Usa assim: !awake 09:20"
        _, day = self._day(now)
        day["awake_at"] = awake_at
        day["notified"] = []
        self.save()
        return f"Dia recalculado a partir de {awake_at}. Compromissos fixos preservados; prioridades baixas foram espremidas primeiro.\n\n{self.format_today(now)}"

    def state(self, now=None):
        now = self._now(now)
        minute = now.hour * 60 + now.minute
        for task in self.schedule(now):
            if self._minutes(task["start"]) <= minute < self._minutes(task["end"]):
                return task
        future = [task for task in self.schedule(now) if self._minutes(task["start"]) > minute]
        return future[0] if future else None

    def stats(self, now=None):
        now = self._now(now)
        _, day = self._day(now)
        done = sum(1 for value in day["tasks"].values() if value == "done")
        skipped = sum(1 for value in day["tasks"].values() if value == "skipped")
        streak = 0
        cursor = now.date()
        while True:
            record = self.data["days"].get(cursor.isoformat())
            if not record or not any(value == "done" for value in record.get("tasks", {}).values()):
                break
            streak += 1
            cursor -= timedelta(days=1)
        return {"done": done, "skipped": skipped, "xp": done * 100, "streak": streak}

    def format_today(self, now=None):
        _, day = self._day(now)
        icons = {"done": "✓", "skipped": "↷"}
        rows = [f"ROTINA {day['routine'].upper()} — HOJE"]
        for task in self.schedule(now):
            marker = icons.get(day["tasks"].get(task["key"]), "·")
            rows.append(f"{marker} {task['start']}–{task['end']}  {task['label']}")
        rows.append("\n!done rust | !skip english | !awake 09:20")
        return "\n".join(rows)

    def format_status(self, now=None):
        current = self.state(now)
        stats = self.stats(now)
        current_text = f"Agora: {current['label']} ({current['start']}–{current['end']})" if current else "Dia encerrado. Vai dormir, criatura."
        return f"{current_text}\nXP hoje: {stats['xp']} | feitos: {stats['done']} | pulados: {stats['skipped']} | streak: {stats['streak']} dia(s)"

    def format_week(self, now=None):
        now = self._now(now)
        start = now.date() - timedelta(days=now.weekday())
        rows, total = ["SEMANA DA MAYA"], 0
        for offset in range(7):
            current = start + timedelta(days=offset)
            record = self.data["days"].get(current.isoformat(), {})
            done = sum(value == "done" for value in record.get("tasks", {}).values())
            total += done * 100
            rows.append(f"{current.strftime('%a %d/%m')}: {done} feitos | {done * 100} XP")
        rows.append(f"Total: {total} XP")
        return "\n".join(rows)

    def due_reminders(self, now=None):
        now = self._now(now)
        if not self.data.get("settings", {}).get("reminders", True):
            return []
        _, day = self._day(now)
        minute = now.hour * 60 + now.minute
        reminders = []
        for task in self.schedule(now):
            if (self._minutes(task["start"]) == minute and task["key"] not in day["notified"]
                    and day["tasks"].get(task["key"]) not in {"done", "skipped"}):
                day["notified"].append(task["key"])
                reminders.append(f"{task['start']}. Hora de {task['label']}.")
        if reminders:
            self.save()
        return reminders
