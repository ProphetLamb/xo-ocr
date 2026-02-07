import datetime
import queue
import sqlite3
import threading
import typing as t


class DBWorker(threading.Thread):
    def __init__(self, db_path: str, task_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.db_path = db_path
        self.task_queue = task_queue
        self.stop_event = stop_event
        self.conn: t.Optional[sqlite3.Connection] = None

    def init_db(self):
        # Connection created on the worker thread
        self.conn = sqlite3.connect(self.db_path, check_same_thread=True)
        cur = self.conn.cursor()
        # Existing table left as-is; create a parts table for the queued items
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                name TEXT,
                category TEXT,
                powerscore INTEGER,
                vehicle_durability INTEGER,
                durability INTEGER,
                mass INTEGER,
                feature_bullet INTEGER,
                feature_explosion INTEGER,
                feature_fire INTEGER,
                feature_cold INTEGER,
                feature_contact INTEGER,
                feature_electric INTEGER,
                feature_passthru INTEGER,
                feature_ram INTEGER
            )
            """
        )
        self.conn.commit()

    def run(self):
        try:
            self.init_db()
            while not self.stop_event.is_set():
                try:
                    info = self.task_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if info is None:
                    # sentinel to stop
                    break
                try:
                    self.save_result(info)
                finally:
                    # mark task done even if save_result raises
                    try:
                        self.task_queue.task_done()
                    except Exception:
                        pass
        finally:
            if self.conn:
                self.conn.close()

    def save_result(self, info: t.Dict[str, t.Any]):
        """
        Persist a single item (dict) into the parts table.
        Expected keys: name, category, powerscore, durability, mass
        Optional keys: feature_bullet, feature_explosion, feature_fire,
                       feature_cold, feature_contact, feature_electric,
                       feature_passthru, feature_ram
        """
        if not self.conn:
            return

        # Use UTC ISO timestamp with trailing Z
        timestamp = datetime.datetime.now(
            datetime.timezone.utc).isoformat() + "Z"

        # Extract required and optional fields, defaulting to None when missing
        name = info.get("name")
        category = info.get("category")
        powerscore = info.get("powerscore")
        durability = info.get("durability")
        vehicle_durability = info.get("vehicle_durability")
        mass = info.get("mass")

        feature_bullet = info.get("feature_bullet")
        feature_explosion = info.get("feature_explosion")
        feature_fire = info.get("feature_fire")
        feature_cold = info.get("feature_cold")
        feature_contact = info.get("feature_contact")
        feature_electric = info.get("feature_electric")
        feature_passthru = info.get("feature_passthru")
        feature_ram = info.get("feature_ram")

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO parts (
                    timestamp, name, category, powerscore, vehicle_durability, durability, mass,
                    feature_bullet, feature_explosion, feature_fire, feature_cold,
                    feature_contact, feature_electric, feature_passthru, feature_ram
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp, name, category, powerscore, vehicle_durability, durability, mass,
                    feature_bullet, feature_explosion, feature_fire, feature_cold,
                    feature_contact, feature_electric, feature_passthru, feature_ram
                )
            )
            self.conn.commit()
            print(f"[*] Saved OCR result")
        except Exception as e:
            print("[!] Error saving OCR result:", e)
            try:
                self.conn.rollback()
            except Exception:
                pass
