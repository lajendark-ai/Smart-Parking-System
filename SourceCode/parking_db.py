"""
Smart Parking System - data and business-logic layer.

All database access and all business rules live here, so the screens in
app.py stay thin and the rules can be unit tested without a GUI.
"""
import hashlib
import math
import os
import random
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_parking.db")
FMT = "%Y-%m-%d %H:%M:%S"

VEHICLE_TYPES = ("Car", "Bike", "Van")
PAY_METHODS = ("Cash", "Online", "Card")
MAX_FAILED_LOGINS = 5
MAX_RESERVE_HOURS = 12


class ParkingError(Exception):
    """Raised for any rule violation. The message is safe to show to the user."""


# --------------------------------------------------------------------- helpers
def now():
    return datetime.now().replace(microsecond=0)


def fmt(dt):
    return dt.strftime(FMT)


# Natural slot order: A1, A2, ... A10 (letter first, then the number as an integer)
SLOT_ORDER = "slot_type, substr(slot_number, 1, 1), CAST(substr(slot_number, 2) AS INTEGER)"
SLOT_ORDER_SHORT = "substr(slot_number, 1, 1), CAST(substr(slot_number, 2) AS INTEGER)"


def parse(text):
    return datetime.strptime(text, FMT)


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ----------------------------------------------------------------- validation
def valid_vehicle_number(value):
    return re.fullmatch(r"[A-Z]{3}-\d{3,4}", value.strip().upper()) is not None


def valid_name(value):
    value = value.strip()
    return 2 <= len(value) <= 50 and value.replace(" ", "").isalpha()


def valid_mobile(value):
    return value.isdigit() and len(value) == 11


def valid_username(value):
    return re.fullmatch(r"[a-z0-9_]{4,20}", value) is not None


def valid_password(value):
    return len(value) >= 6


# ------------------------------------------------------------------- password
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 60_000).hex()
    return salt, digest


# --------------------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    username        TEXT NOT NULL UNIQUE,
    salt            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('Manager','Staff','User')),
    phone           TEXT,
    status          TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Disabled','Locked')),
    failed_logins   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number  TEXT NOT NULL UNIQUE,
    vehicle_type    TEXT NOT NULL CHECK (vehicle_type IN ('Car','Bike','Van')),
    owner_name      TEXT NOT NULL,
    phone           TEXT NOT NULL,
    user_id         INTEGER REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS slots (
    slot_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_number     TEXT NOT NULL UNIQUE,
    slot_type       TEXT NOT NULL CHECK (slot_type IN ('Car','Bike','Van')),
    slot_status     TEXT NOT NULL DEFAULT 'Available' CHECK (slot_status IN ('Available','Occupied','Reserved'))
);
CREATE TABLE IF NOT EXISTS rates (
    vehicle_type    TEXT PRIMARY KEY CHECK (vehicle_type IN ('Car','Bike','Van')),
    hourly_rate     INTEGER NOT NULL CHECK (hourly_rate > 0)
);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(user_id),
    vehicle_id      INTEGER NOT NULL REFERENCES vehicles(vehicle_id),
    slot_id         INTEGER NOT NULL REFERENCES slots(slot_id),
    start_time      TEXT NOT NULL,
    end_time        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Cancelled','Completed','Expired'))
);
CREATE TABLE IF NOT EXISTS parking (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id      INTEGER NOT NULL REFERENCES vehicles(vehicle_id),
    slot_id         INTEGER NOT NULL REFERENCES slots(slot_id),
    staff_id        INTEGER NOT NULL REFERENCES users(user_id),
    entry_time      TEXT NOT NULL,
    exit_time       TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id       INTEGER NOT NULL UNIQUE REFERENCES parking(record_id),
    amount          INTEGER NOT NULL CHECK (amount >= 0),
    payment_date    TEXT NOT NULL,
    payment_method  TEXT NOT NULL CHECK (payment_method IN ('Cash','Online','Card'))
);
"""


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


# ------------------------------------------------------------- access control
def _require(conn, actor_id, *roles):
    row = conn.execute("SELECT role, status FROM users WHERE user_id=?", (actor_id,)).fetchone()
    if row is None or row["status"] != "Active" or row["role"] not in roles:
        raise ParkingError("You do not have permission to perform this action.")
    return row


def authenticate(conn, username, password, role):
    username = username.strip().lower()
    if not username or not password:
        raise ParkingError("Enter both username and password.")
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    generic = "Invalid username or password."
    if user is None or user["role"] != role:
        raise ParkingError(generic)
    if user["status"] == "Disabled":
        raise ParkingError("This account is disabled. Contact the manager.")
    if user["status"] == "Locked":
        raise ParkingError("Account locked after too many failed attempts. Contact the manager.")
    _, digest = hash_password(password, user["salt"])
    if digest != user["password_hash"]:
        failed = user["failed_logins"] + 1
        status = "Locked" if failed >= MAX_FAILED_LOGINS else "Active"
        conn.execute("UPDATE users SET failed_logins=?, status=? WHERE user_id=?",
                     (failed, status, user["user_id"]))
        conn.commit()
        raise ParkingError(generic)
    conn.execute("UPDATE users SET failed_logins=0 WHERE user_id=?", (user["user_id"],))
    conn.commit()
    return user


def _create_account(conn, full_name, username, password, phone, role):
    full_name, username, phone = full_name.strip(), username.strip().lower(), phone.strip()
    if not valid_name(full_name):
        raise ParkingError("Full name must contain only letters (2-50 characters).")
    if not valid_username(username):
        raise ParkingError("Username must be 4-20 characters: lowercase letters, digits, underscore.")
    if not valid_password(password):
        raise ParkingError("Password must be at least 6 characters.")
    if not valid_mobile(phone):
        raise ParkingError("Mobile number must be exactly 11 digits.")
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        raise ParkingError("That username is already taken.")
    salt, digest = hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (full_name, username, salt, password_hash, role, phone) VALUES (?,?,?,?,?,?)",
        (full_name, username, salt, digest, role, phone))
    conn.commit()
    return cur.lastrowid


def register_user(conn, full_name, username, password, phone):
    return _create_account(conn, full_name, username, password, phone, "User")


def add_staff(conn, actor_id, full_name, username, password, phone):
    _require(conn, actor_id, "Manager")
    return _create_account(conn, full_name, username, password, phone, "Staff")


def set_account_status(conn, actor_id, user_id, status):
    _require(conn, actor_id, "Manager")
    if status not in ("Active", "Disabled"):
        raise ParkingError("Invalid status.")
    if user_id == actor_id:
        raise ParkingError("You cannot change your own account status.")
    target = conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
    if target is None:
        raise ParkingError("Account not found.")
    if target["role"] == "Manager":
        raise ParkingError("Manager accounts cannot be changed here.")
    conn.execute("UPDATE users SET status=?, failed_logins=0 WHERE user_id=?", (status, user_id))
    conn.commit()


# -------------------------------------------------------------------- tariff
def get_rate(conn, vehicle_type):
    row = conn.execute("SELECT hourly_rate FROM rates WHERE vehicle_type=?", (vehicle_type,)).fetchone()
    if row is None:
        raise ParkingError("No tariff is defined for this vehicle type.")
    return row["hourly_rate"]


def set_rate(conn, actor_id, vehicle_type, rate):
    _require(conn, actor_id, "Manager")
    if vehicle_type not in VEHICLE_TYPES:
        raise ParkingError("Select a valid vehicle type.")
    try:
        rate = int(str(rate).strip())
    except ValueError:
        raise ParkingError("Rate must be a whole number.")
    if not 1 <= rate <= 10000:
        raise ParkingError("Rate must be between 1 and 10,000 per hour.")
    conn.execute("UPDATE rates SET hourly_rate=? WHERE vehicle_type=?", (rate, vehicle_type))
    conn.commit()


def calculate_fee(entry, exit_, hourly_rate):
    """Fee is charged per started hour, with a minimum of one hour."""
    if exit_ < entry:
        raise ParkingError("Exit time cannot be earlier than entry time.")
    hours = max(1, math.ceil((exit_ - entry).total_seconds() / 3600))
    return hours, hours * hourly_rate


# --------------------------------------------------------------------- slots
def add_slot(conn, actor_id, slot_number, slot_type):
    _require(conn, actor_id, "Manager")
    slot_number = slot_number.strip().upper()
    if not re.fullmatch(r"[A-Z][0-9]{1,3}", slot_number):
        raise ParkingError("Slot number must be a letter followed by 1-3 digits, e.g. A12.")
    if slot_type not in VEHICLE_TYPES:
        raise ParkingError("Select a valid slot type.")
    if conn.execute("SELECT 1 FROM slots WHERE slot_number=?", (slot_number,)).fetchone():
        raise ParkingError("A slot with this number already exists.")
    conn.execute("INSERT INTO slots (slot_number, slot_type) VALUES (?,?)", (slot_number, slot_type))
    conn.commit()


def remove_slot(conn, actor_id, slot_id):
    _require(conn, actor_id, "Manager")
    slot = conn.execute("SELECT * FROM slots WHERE slot_id=?", (slot_id,)).fetchone()
    if slot is None:
        raise ParkingError("Slot not found.")
    if slot["slot_status"] != "Available":
        raise ParkingError("Only an available slot can be removed.")
    used = conn.execute("SELECT 1 FROM parking WHERE slot_id=? UNION SELECT 1 FROM reservations WHERE slot_id=?",
                        (slot_id, slot_id)).fetchone()
    if used:
        raise ParkingError("This slot has parking history and cannot be removed.")
    conn.execute("DELETE FROM slots WHERE slot_id=?", (slot_id,))
    conn.commit()


def slots_list(conn):
    return conn.execute(f"SELECT * FROM slots ORDER BY {SLOT_ORDER}").fetchall()


def free_slot_counts(conn):
    expire_reservations(conn)
    counts = {t: 0 for t in VEHICLE_TYPES}
    for r in conn.execute("SELECT slot_type, COUNT(*) c FROM slots WHERE slot_status='Available' GROUP BY slot_type"):
        counts[r["slot_type"]] = r["c"]
    return counts


# ------------------------------------------------------------------ vehicles
def add_vehicle(conn, user_id, number, vehicle_type, owner, phone):
    _require(conn, user_id, "User")
    number, owner, phone = number.strip().upper(), owner.strip(), phone.strip()
    _check_vehicle_fields(number, vehicle_type, owner, phone)
    row = conn.execute("SELECT * FROM vehicles WHERE vehicle_number=?", (number,)).fetchone()
    if row is not None:
        if row["user_id"] not in (None, user_id):
            raise ParkingError("This vehicle number is registered to another account.")
        if row["user_id"] is None:  # vehicle already known from the gate: claim it
            conn.execute("UPDATE vehicles SET user_id=? WHERE vehicle_id=?", (user_id, row["vehicle_id"]))
            conn.commit()
            return row["vehicle_id"]
        raise ParkingError("You have already registered this vehicle.")
    cur = conn.execute("INSERT INTO vehicles (vehicle_number, vehicle_type, owner_name, phone, user_id) VALUES (?,?,?,?,?)",
                       (number, vehicle_type, owner, phone, user_id))
    conn.commit()
    return cur.lastrowid


def _check_vehicle_fields(number, vehicle_type, owner, phone):
    if not (number and vehicle_type and owner and phone):
        raise ParkingError("Fill in all required fields.")
    if not valid_vehicle_number(number):
        raise ParkingError("Vehicle number format must be like ABC-123.")
    if vehicle_type not in VEHICLE_TYPES:
        raise ParkingError("Select a valid vehicle type.")
    if not valid_name(owner):
        raise ParkingError("Owner name must contain only letters.")
    if not valid_mobile(phone):
        raise ParkingError("Mobile number must be exactly 11 digits.")


def user_vehicles(conn, user_id):
    return conn.execute("SELECT * FROM vehicles WHERE user_id=? ORDER BY vehicle_number", (user_id,)).fetchall()


def _is_parked(conn, vehicle_id):
    return conn.execute("SELECT 1 FROM parking WHERE vehicle_id=? AND exit_time IS NULL", (vehicle_id,)).fetchone() is not None


# -------------------------------------------------------------- reservations
def expire_reservations(conn):
    """Release slots held by reservations whose time window has passed."""
    stamp = fmt(now())
    rows = conn.execute("SELECT reservation_id, slot_id FROM reservations WHERE status='Active' AND end_time < ?",
                        (stamp,)).fetchall()
    for r in rows:
        conn.execute("UPDATE reservations SET status='Expired' WHERE reservation_id=?", (r["reservation_id"],))
        conn.execute("UPDATE slots SET slot_status='Available' WHERE slot_id=? AND slot_status='Reserved'", (r["slot_id"],))
    if rows:
        conn.commit()


def reserve_slot(conn, user_id, vehicle_id, hours):
    _require(conn, user_id, "User")
    expire_reservations(conn)
    try:
        hours = int(str(hours).strip())
    except ValueError:
        raise ParkingError("Duration must be a whole number of hours.")
    if not 1 <= hours <= MAX_RESERVE_HOURS:
        raise ParkingError(f"Duration must be between 1 and {MAX_RESERVE_HOURS} hours.")
    vehicle = conn.execute("SELECT * FROM vehicles WHERE vehicle_id=? AND user_id=?", (vehicle_id, user_id)).fetchone()
    if vehicle is None:
        raise ParkingError("Select one of your registered vehicles.")
    if _is_parked(conn, vehicle_id):
        raise ParkingError("This vehicle is already parked.")
    if conn.execute("SELECT 1 FROM reservations WHERE vehicle_id=? AND status='Active'", (vehicle_id,)).fetchone():
        raise ParkingError("This vehicle already has an active reservation.")
    slot = conn.execute(f"SELECT * FROM slots WHERE slot_type=? AND slot_status='Available' ORDER BY {SLOT_ORDER_SHORT} LIMIT 1",
                        (vehicle["vehicle_type"],)).fetchone()
    if slot is None:
        raise ParkingError(f"No {vehicle['vehicle_type']} slot is available right now.")
    start = now()
    cur = conn.execute(
        "INSERT INTO reservations (user_id, vehicle_id, slot_id, start_time, end_time) VALUES (?,?,?,?,?)",
        (user_id, vehicle_id, slot["slot_id"], fmt(start), fmt(start + timedelta(hours=hours))))
    conn.execute("UPDATE slots SET slot_status='Reserved' WHERE slot_id=?", (slot["slot_id"],))
    conn.commit()
    return {"reservation_id": cur.lastrowid, "slot_number": slot["slot_number"]}


def cancel_reservation(conn, user_id, reservation_id):
    _require(conn, user_id, "User")
    res = conn.execute("SELECT * FROM reservations WHERE reservation_id=? AND user_id=?",
                       (reservation_id, user_id)).fetchone()
    if res is None:
        raise ParkingError("Reservation not found.")
    if res["status"] != "Active":
        raise ParkingError("Only an active reservation can be cancelled.")
    conn.execute("UPDATE reservations SET status='Cancelled' WHERE reservation_id=?", (reservation_id,))
    conn.execute("UPDATE slots SET slot_status='Available' WHERE slot_id=? AND slot_status='Reserved'", (res["slot_id"],))
    conn.commit()


def reservations_list(conn, user_id=None, active_only=False):
    expire_reservations(conn)
    sql = """SELECT r.reservation_id, v.vehicle_number, s.slot_number, r.start_time, r.end_time, r.status
             FROM reservations r JOIN vehicles v ON v.vehicle_id=r.vehicle_id JOIN slots s ON s.slot_id=r.slot_id"""
    where, args = [], []
    if user_id is not None:
        where.append("r.user_id=?"); args.append(user_id)
    if active_only:
        where.append("r.status='Active'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return conn.execute(sql + " ORDER BY r.reservation_id DESC", args).fetchall()


# ------------------------------------------------------------- entry and exit
def park_vehicle(conn, staff_id, number, vehicle_type, owner, phone):
    _require(conn, staff_id, "Staff", "Manager")
    expire_reservations(conn)
    number, owner, phone = number.strip().upper(), owner.strip(), phone.strip()
    _check_vehicle_fields(number, vehicle_type, owner, phone)
    vehicle = conn.execute("SELECT * FROM vehicles WHERE vehicle_number=?", (number,)).fetchone()
    if vehicle is None:
        cur = conn.execute("INSERT INTO vehicles (vehicle_number, vehicle_type, owner_name, phone) VALUES (?,?,?,?)",
                           (number, vehicle_type, owner, phone))
        vehicle_id = cur.lastrowid
    else:
        vehicle_id = vehicle["vehicle_id"]
        if vehicle["vehicle_type"] != vehicle_type:
            conn.rollback()
            raise ParkingError(f"This vehicle is registered as a {vehicle['vehicle_type']}.")
        if _is_parked(conn, vehicle_id):
            conn.rollback()
            raise ParkingError("This vehicle is already parked.")
    reserved = conn.execute("SELECT * FROM reservations WHERE vehicle_id=? AND status='Active'", (vehicle_id,)).fetchone()
    if reserved:
        slot_id = reserved["slot_id"]
        conn.execute("UPDATE reservations SET status='Completed' WHERE reservation_id=?", (reserved["reservation_id"],))
    else:
        slot = conn.execute(f"SELECT slot_id FROM slots WHERE slot_type=? AND slot_status='Available' ORDER BY {SLOT_ORDER_SHORT} LIMIT 1",
                            (vehicle_type,)).fetchone()
        if slot is None:
            conn.rollback()
            raise ParkingError(f"No {vehicle_type} slot is available.")
        slot_id = slot["slot_id"]
    cur = conn.execute("INSERT INTO parking (vehicle_id, slot_id, staff_id, entry_time) VALUES (?,?,?,?)",
                       (vehicle_id, slot_id, staff_id, fmt(now())))
    conn.execute("UPDATE slots SET slot_status='Occupied' WHERE slot_id=?", (slot_id,))
    conn.commit()
    slot_number = conn.execute("SELECT slot_number FROM slots WHERE slot_id=?", (slot_id,)).fetchone()[0]
    return {"record_id": cur.lastrowid, "slot_number": slot_number, "reserved": bool(reserved)}


def _active_record(conn, number):
    number = number.strip().upper()
    if not number:
        raise ParkingError("Enter the vehicle number.")
    if not valid_vehicle_number(number):
        raise ParkingError("Vehicle number format must be like ABC-123.")
    vehicle = conn.execute("SELECT * FROM vehicles WHERE vehicle_number=?", (number,)).fetchone()
    if vehicle is None:
        raise ParkingError("Vehicle not found.")
    rec = conn.execute("""SELECT p.*, s.slot_number FROM parking p JOIN slots s ON s.slot_id=p.slot_id
                          WHERE p.vehicle_id=? AND p.exit_time IS NULL""", (vehicle["vehicle_id"],)).fetchone()
    if rec is None:
        raise ParkingError("No active parking record for this vehicle.")
    return vehicle, rec


def quote_exit(conn, number, at=None):
    vehicle, rec = _active_record(conn, number)
    at = at or now()
    entry = parse(rec["entry_time"])
    hours, amount = calculate_fee(entry, at, get_rate(conn, vehicle["vehicle_type"]))
    return {"record_id": rec["record_id"], "vehicle_number": vehicle["vehicle_number"], "slot_number": rec["slot_number"],
            "entry_time": rec["entry_time"], "exit_time": fmt(at), "hours": hours, "amount": amount}


def exit_vehicle(conn, staff_id, number, method, at=None):
    _require(conn, staff_id, "Staff", "Manager")
    if method not in PAY_METHODS:
        raise ParkingError("Select a payment method.")
    quote = quote_exit(conn, number, at)
    rec = conn.execute("SELECT slot_id FROM parking WHERE record_id=?", (quote["record_id"],)).fetchone()
    conn.execute("UPDATE parking SET exit_time=? WHERE record_id=?", (quote["exit_time"], quote["record_id"]))
    conn.execute("INSERT INTO payments (record_id, amount, payment_date, payment_method) VALUES (?,?,?,?)",
                 (quote["record_id"], quote["amount"], quote["exit_time"][:10], method))
    conn.execute("UPDATE slots SET slot_status='Available' WHERE slot_id=?", (rec["slot_id"],))
    conn.commit()
    return quote


# ------------------------------------------------------------------- queries
def active_parking(conn):
    return conn.execute("""SELECT v.vehicle_number, v.vehicle_type, v.owner_name, s.slot_number, p.entry_time
                           FROM parking p JOIN vehicles v ON v.vehicle_id=p.vehicle_id JOIN slots s ON s.slot_id=p.slot_id
                           WHERE p.exit_time IS NULL ORDER BY p.entry_time DESC""").fetchall()


def parking_records(conn, user_id=None, limit=500):
    sql = """SELECT p.record_id, v.vehicle_number, s.slot_number, p.entry_time, p.exit_time, IFNULL(pay.amount, '') AS amount
             FROM parking p JOIN vehicles v ON v.vehicle_id=p.vehicle_id JOIN slots s ON s.slot_id=p.slot_id
             LEFT JOIN payments pay ON pay.record_id=p.record_id"""
    args = []
    if user_id is not None:
        sql += " WHERE v.user_id=?"
        args.append(user_id)
    return conn.execute(sql + " ORDER BY p.record_id DESC LIMIT ?", args + [limit]).fetchall()


def payments_list(conn, limit=500):
    return conn.execute("""SELECT pay.payment_id, v.vehicle_number, pay.amount, pay.payment_date, pay.payment_method
                           FROM payments pay JOIN parking p ON p.record_id=pay.record_id
                           JOIN vehicles v ON v.vehicle_id=p.vehicle_id ORDER BY pay.payment_id DESC LIMIT ?""", (limit,)).fetchall()


def accounts_list(conn):
    return conn.execute("SELECT user_id, full_name, username, role, phone, status FROM users ORDER BY role, full_name").fetchall()


def rates_list(conn):
    return conn.execute("SELECT * FROM rates ORDER BY vehicle_type").fetchall()


def summary(conn):
    total = conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
    occupied = conn.execute("SELECT COUNT(*) FROM parking WHERE exit_time IS NULL").fetchone()[0]
    revenue = conn.execute("SELECT IFNULL(SUM(amount),0) FROM payments").fetchone()[0]
    return {"total_slots": total, "occupied": occupied, "available": total - occupied, "revenue": revenue}


# ------------------------------------------------------------------ sample data
def seed_demo(conn):
    """Fill an empty database with demo accounts, slots, tariff and history."""
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    rnd = random.Random(2403)
    manager = _create_account(conn, "Bilal Ahmed", "manager", "manager123", "03001112233", "Manager")
    staff_ids = [_create_account(conn, "Hassan Raza", "staff", "staff123", "03111112233", "Staff"),
                 _create_account(conn, "Imran Shah", "staff2", "staff123", "03221112233", "Staff")]
    user_names = [("Ali Khan", "user", "03331112233"), ("Sara Malik", "sara_m", "03441112233"),
                  ("Zain Qureshi", "zain_q", "03551112233"), ("Fatima Noor", "fatima_n", "03661112233")]
    user_ids = [_create_account(conn, n, u, "user123", p, "User") for n, u, p in user_names]

    for t, r in (("Car", 100), ("Bike", 50), ("Van", 150)):
        conn.execute("INSERT INTO rates VALUES (?,?)", (t, r))
    layout = (("A", "Car", 10), ("B", "Bike", 8), ("C", "Van", 6))
    for prefix, t, n in layout:
        for i in range(1, n + 1):
            conn.execute("INSERT INTO slots (slot_number, slot_type) VALUES (?,?)", (f"{prefix}{i}", t))

    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    vehicles = []
    owners = ["Ahmed Raza", "Hina Tariq", "Omar Farooq", "Kiran Ali", "Usman Ghani", "Ayesha Siddiq", "Bilal Hussain",
              "Mariam Zahid", "Danish Iqbal", "Nida Shah", "Faisal Mehmood", "Rabia Anwar", "Saad Karim", "Laiba Jamil"]
    for i in range(26):
        t = ("Car", "Car", "Bike", "Van")[i % 4]
        num = "".join(rnd.choice(letters) for _ in range(3)) + f"-{rnd.randint(100, 9999)}"
        if i < 4:
            owner, phone, uid = user_names[i][0], user_names[i][2], user_ids[i]
        else:
            owner, phone, uid = owners[i % len(owners)], "03" + "".join(str(rnd.randint(0, 9)) for _ in range(9)), None
        cur = conn.execute("INSERT INTO vehicles (vehicle_number, vehicle_type, owner_name, phone, user_id) VALUES (?,?,?,?,?)",
                           (num, t, owner, phone, uid))
        vehicles.append((cur.lastrowid, t))
    slots_by_type = {t: [r[0] for r in conn.execute(f"SELECT slot_id FROM slots WHERE slot_type=? ORDER BY {SLOT_ORDER_SHORT}", (t,))]
                     for t in VEHICLE_TYPES}
    rates = {t: r for t, r in conn.execute("SELECT vehicle_type, hourly_rate FROM rates")}

    def record(vid, vtype, entry, hours_spent):
        exit_ = entry + timedelta(minutes=hours_spent)
        _, amount = calculate_fee(entry, exit_, rates[vtype])
        cur = conn.execute("INSERT INTO parking (vehicle_id, slot_id, staff_id, entry_time, exit_time) VALUES (?,?,?,?,?)",
                           (vid, rnd.choice(slots_by_type[vtype]), rnd.choice(staff_ids), fmt(entry), fmt(exit_)))
        conn.execute("INSERT INTO payments (record_id, amount, payment_date, payment_method) VALUES (?,?,?,?)",
                     (cur.lastrowid, amount, fmt(exit_)[:10], rnd.choices(PAY_METHODS, weights=(55, 30, 15))[0]))

    today = now().replace(hour=0, minute=0, second=0)
    for back in range(150, 0, -1):  # history: last 150 days, grows toward today
        day = today - timedelta(days=back)
        for _ in range(rnd.randint(2, 5) + (150 - back) // 40):
            vid, vtype = rnd.choice(vehicles)
            record(vid, vtype, day + timedelta(hours=rnd.randint(6, 19), minutes=rnd.randint(0, 59)), rnd.randint(40, 300))
    cur_hour = now().hour
    for _ in range(9):  # completed visits earlier today
        if cur_hour < 2:
            break
        vid, vtype = rnd.choice(vehicles)
        h = rnd.randint(0, cur_hour - 1)
        record(vid, vtype, today + timedelta(hours=h, minutes=rnd.randint(0, 59)), rnd.randint(20, 55))
    # vehicles parked right now
    for vid, vtype in vehicles[-6:]:
        slot = conn.execute(f"SELECT slot_id FROM slots WHERE slot_type=? AND slot_status='Available' ORDER BY {SLOT_ORDER_SHORT} LIMIT 1",
                            (vtype,)).fetchone()[0]
        entry = max(today, now() - timedelta(minutes=rnd.randint(10, 150)))
        conn.execute("INSERT INTO parking (vehicle_id, slot_id, staff_id, entry_time) VALUES (?,?,?,?)",
                     (vid, slot, staff_ids[0], fmt(entry)))
        conn.execute("UPDATE slots SET slot_status='Occupied' WHERE slot_id=?", (slot,))
    conn.commit()
    return manager


def open_database(path=None, seed=True):
    conn = connect(path)
    init_db(conn)
    if seed:
        seed_demo(conn)
    return conn
