"""Automated tests for the Smart Parking System business logic.
Run:  python -m unittest discover -s Tests -v   (from the project root)
Each test docstring starts with its test-case ID used in the Test Report."""
import os, sys, unittest
from datetime import timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SourceCode"))
import parking_db as db
from parking_db import ParkingError


def fresh():
    conn = db.open_database(":memory:", seed=False)
    m = db._create_account(conn, "Bilal Ahmed", "manager", "manager123", "03001112233", "Manager")
    s = db._create_account(conn, "Hassan Raza", "staff", "staff123", "03111112233", "Staff")
    u = db.register_user(conn, "Ali Khan", "aliuser", "user123", "03331112233")
    for t, r in (("Car", 100), ("Bike", 50), ("Van", 150)):
        conn.execute("INSERT INTO rates VALUES (?,?)", (t, r))
    for n, t in (("A1", "Car"), ("A2", "Car"), ("B1", "Bike"), ("C1", "Van")):
        conn.execute("INSERT INTO slots (slot_number, slot_type) VALUES (?,?)", (n, t))
    conn.commit()
    return conn, m, s, u


class AuthTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh()

    def test_TC01_valid_login(self):
        """TC-01 Valid credentials log in for the matching role"""
        self.assertEqual(db.authenticate(self.c, "staff", "staff123", "Staff")["user_id"], self.s)

    def test_TC02_wrong_password(self):
        """TC-02 Wrong password is rejected with a generic message"""
        with self.assertRaisesRegex(ParkingError, "Invalid username or password"):
            db.authenticate(self.c, "staff", "bad-pass", "Staff")

    def test_TC03_role_mismatch(self):
        """TC-03 A Staff account cannot sign in through the Manager login"""
        with self.assertRaisesRegex(ParkingError, "Invalid username or password"):
            db.authenticate(self.c, "staff", "staff123", "Manager")

    def test_TC04_empty_fields(self):
        """TC-04 Empty username or password is rejected"""
        with self.assertRaisesRegex(ParkingError, "Enter both"):
            db.authenticate(self.c, "", "", "User")

    def test_TC05_lockout_after_five_failures(self):
        """TC-05 Account locks after 5 failed attempts (boundary)"""
        for _ in range(5):
            with self.assertRaises(ParkingError):
                db.authenticate(self.c, "aliuser", "wrong1", "User")
        with self.assertRaisesRegex(ParkingError, "locked"):
            db.authenticate(self.c, "aliuser", "user123", "User")

    def test_TC06_passwords_are_hashed(self):
        """TC-06 Passwords are never stored in plain text"""
        row = self.c.execute("SELECT password_hash FROM users WHERE username='aliuser'").fetchone()
        self.assertNotIn("user123", row[0])
        self.assertEqual(len(row[0]), 64)


class RegistrationTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh()

    def test_TC07_register_valid_user(self):
        """TC-07 A new user can register with valid details"""
        self.assertGreater(db.register_user(self.c, "Sara Malik", "sara_m", "secret1", "03441112233"), 0)

    def test_TC08_duplicate_username(self):
        """TC-08 Duplicate username is rejected"""
        with self.assertRaisesRegex(ParkingError, "already taken"):
            db.register_user(self.c, "Other Person", "aliuser", "secret1", "03441112233")

    def test_TC09_invalid_fields(self):
        """TC-09 Invalid name, username, password and mobile are rejected"""
        bad = [("Al1", "okname1", "secret1", "03441112233", "letters"),
               ("Sara Malik", "AB", "secret1", "03441112233", "Username"),
               ("Sara Malik", "sara_m", "123", "03441112233", "Password"),
               ("Sara Malik", "sara_m", "secret1", "0344111", "11 digits")]
        for name, user, pw, ph, msg in bad:
            with self.assertRaisesRegex(ParkingError, msg):
                db.register_user(self.c, name, user, pw, ph)

    def test_TC10_manager_adds_staff(self):
        """TC-10 Manager can create a staff account"""
        self.assertGreater(db.add_staff(self.c, self.m, "Imran Shah", "staff2", "staff123", "03221112233"), 0)

    def test_TC11_staff_cannot_add_staff(self):
        """TC-11 Staff and User roles are denied manager functions"""
        for actor in (self.s, self.u):
            with self.assertRaisesRegex(ParkingError, "permission"):
                db.add_staff(self.c, actor, "Imran Shah", "staff2", "staff123", "03221112233")


class VehicleTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh()

    def test_TC12_add_vehicle(self):
        """TC-12 User registers a vehicle"""
        vid = db.add_vehicle(self.c, self.u, "abc-123", "Car", "Ali Khan", "03331112233")
        self.assertEqual(db.user_vehicles(self.c, self.u)[0]["vehicle_id"], vid)
        self.assertEqual(db.user_vehicles(self.c, self.u)[0]["vehicle_number"], "ABC-123")

    def test_TC13_invalid_vehicle_number(self):
        """TC-13 Invalid vehicle number formats are rejected"""
        for bad in ("12-ABC", "ABCD-123", "AB-1234", "ABC123", "ABC-12", "ABC-12345"):
            with self.assertRaisesRegex(ParkingError, "format"):
                db.add_vehicle(self.c, self.u, bad, "Car", "Ali Khan", "03331112233")

    def test_TC14_duplicate_vehicle(self):
        """TC-14 The same vehicle cannot be registered twice"""
        db.add_vehicle(self.c, self.u, "ABC-123", "Car", "Ali Khan", "03331112233")
        with self.assertRaisesRegex(ParkingError, "already registered"):
            db.add_vehicle(self.c, self.u, "ABC-123", "Car", "Ali Khan", "03331112233")


class ParkingTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh()

    def park(self, num="LEA-101", t="Car"):
        return db.park_vehicle(self.c, self.s, num, t, "Ahmed Raza", "03001234567")

    def test_TC15_entry_assigns_slot(self):
        """TC-15 Vehicle entry assigns the first free slot of its type"""
        r = self.park()
        self.assertEqual(r["slot_number"], "A1")
        status = self.c.execute("SELECT slot_status FROM slots WHERE slot_number='A1'").fetchone()[0]
        self.assertEqual(status, "Occupied")

    def test_TC16_duplicate_entry(self):
        """TC-16 A parked vehicle cannot enter again"""
        self.park()
        with self.assertRaisesRegex(ParkingError, "already parked"):
            self.park()

    def test_TC17_no_free_slot(self):
        """TC-17 Entry fails with a clear message when no slot of that type is free"""
        self.park("AAA-111", "Van")
        with self.assertRaisesRegex(ParkingError, "No Van slot"):
            self.park("BBB-222", "Van")

    def test_TC18_type_mismatch(self):
        """TC-18 A known vehicle cannot enter under a different type"""
        self.park("LEA-101", "Car")
        db.exit_vehicle(self.c, self.s, "LEA-101", "Cash")
        with self.assertRaisesRegex(ParkingError, "registered as a Car"):
            self.park("LEA-101", "Van")

    def test_TC19_entry_validation(self):
        """TC-19 Entry form validates number, owner and mobile"""
        with self.assertRaises(ParkingError): db.park_vehicle(self.c, self.s, "", "Car", "Ahmed Raza", "03001234567")
        with self.assertRaises(ParkingError): db.park_vehicle(self.c, self.s, "LEA-101", "Car", "Ahmed 9", "03001234567")
        with self.assertRaises(ParkingError): db.park_vehicle(self.c, self.s, "LEA-101", "Car", "Ahmed Raza", "123")

    def test_TC20_user_cannot_park(self):
        """TC-20 A User account cannot record vehicle entry"""
        with self.assertRaisesRegex(ParkingError, "permission"):
            db.park_vehicle(self.c, self.u, "LEA-101", "Car", "Ahmed Raza", "03001234567")

    def test_TC21_exit_frees_slot_and_records_payment(self):
        """TC-21 Exit releases the slot and stores one payment"""
        self.park()
        q = db.exit_vehicle(self.c, self.s, "LEA-101", "Online")
        self.assertEqual(q["amount"], 100)
        self.assertEqual(self.c.execute("SELECT slot_status FROM slots WHERE slot_number='A1'").fetchone()[0], "Available")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM payments").fetchone()[0], 1)

    def test_TC22_exit_unknown_or_not_parked(self):
        """TC-22 Exit for an unknown or not-parked vehicle shows an error"""
        with self.assertRaisesRegex(ParkingError, "not found"): db.exit_vehicle(self.c, self.s, "ZZZ-999", "Cash")
        self.park(); db.exit_vehicle(self.c, self.s, "LEA-101", "Cash")
        with self.assertRaisesRegex(ParkingError, "No active parking"): db.exit_vehicle(self.c, self.s, "LEA-101", "Cash")

    def test_TC23_invalid_payment_method(self):
        """TC-23 Exit requires a valid payment method"""
        self.park()
        with self.assertRaisesRegex(ParkingError, "payment method"): db.exit_vehicle(self.c, self.s, "LEA-101", "Cheque")


class FeeTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh(); self.t0 = db.now()

    def test_TC24_fee_boundaries(self):
        """TC-24 Fee uses started hours with a one-hour minimum (boundary values)"""
        cases = [(0, 1), (1, 1), (59, 1), (60, 1), (61, 2), (120, 2), (121, 3)]
        for minutes, hours in cases:
            h, amt = db.calculate_fee(self.t0, self.t0 + timedelta(minutes=minutes), 100)
            self.assertEqual((h, amt), (hours, hours * 100), f"{minutes} min")

    def test_TC25_fee_negative_duration(self):
        """TC-25 Exit time before entry time is rejected"""
        with self.assertRaises(ParkingError):
            db.calculate_fee(self.t0, self.t0 - timedelta(minutes=1), 100)

    def test_TC26_fee_follows_vehicle_type(self):
        """TC-26 Fee depends on the vehicle type tariff"""
        db.park_vehicle(self.c, self.s, "BKE-111", "Bike", "Ahmed Raza", "03001234567")
        q = db.quote_exit(self.c, "BKE-111", at=db.now() + timedelta(minutes=130))
        self.assertEqual((q["hours"], q["amount"]), (3, 150))

    def test_TC27_manager_changes_rate(self):
        """TC-27 Manager can change a rate; invalid rates are rejected"""
        db.set_rate(self.c, self.m, "Car", "120")
        self.assertEqual(db.get_rate(self.c, "Car"), 120)
        for bad in ("0", "-5", "abc", "10001", ""):
            with self.assertRaises(ParkingError): db.set_rate(self.c, self.m, "Car", bad)
        with self.assertRaises(ParkingError): db.set_rate(self.c, self.s, "Car", "100")


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.c, self.m, self.s, self.u = fresh()
        self.v = db.add_vehicle(self.c, self.u, "ABC-123", "Car", "Ali Khan", "03331112233")

    def test_TC28_reserve_slot(self):
        """TC-28 User reserves a slot; the slot becomes Reserved"""
        r = db.reserve_slot(self.c, self.u, self.v, 2)
        self.assertEqual(r["slot_number"], "A1")
        self.assertEqual(self.c.execute("SELECT slot_status FROM slots WHERE slot_number='A1'").fetchone()[0], "Reserved")

    def test_TC29_duration_limits(self):
        """TC-29 Reservation duration must be 1-12 hours (boundary values)"""
        for bad in (0, 13, "x", -1):
            with self.assertRaises(ParkingError): db.reserve_slot(self.c, self.u, self.v, bad)
        db.reserve_slot(self.c, self.u, self.v, 12)

    def test_TC30_one_active_reservation(self):
        """TC-30 A vehicle cannot hold two active reservations"""
        db.reserve_slot(self.c, self.u, self.v, 1)
        with self.assertRaisesRegex(ParkingError, "already has an active"): db.reserve_slot(self.c, self.u, self.v, 1)

    def test_TC31_cancel_releases_slot(self):
        """TC-31 Cancelling a reservation frees the slot"""
        rid = db.reserve_slot(self.c, self.u, self.v, 1)["reservation_id"]
        db.cancel_reservation(self.c, self.u, rid)
        self.assertEqual(self.c.execute("SELECT slot_status FROM slots WHERE slot_number='A1'").fetchone()[0], "Available")
        with self.assertRaisesRegex(ParkingError, "active reservation"): db.cancel_reservation(self.c, self.u, rid)

    def test_TC32_entry_uses_reserved_slot(self):
        """TC-32 Entry of a reserved vehicle uses its reserved slot and completes the reservation"""
        db.reserve_slot(self.c, self.u, self.v, 2)
        r = db.park_vehicle(self.c, self.s, "ABC-123", "Car", "Ali Khan", "03331112233")
        self.assertTrue(r["reserved"]); self.assertEqual(r["slot_number"], "A1")
        self.assertEqual(db.reservations_list(self.c, self.u)[0]["status"], "Completed")

    def test_TC33_reserved_slot_not_given_to_others(self):
        """TC-33 A reserved slot is not assigned to another vehicle"""
        db.reserve_slot(self.c, self.u, self.v, 2)
        r = db.park_vehicle(self.c, self.s, "XYZ-555", "Car", "Ahmed Raza", "03001234567")
        self.assertEqual(r["slot_number"], "A2")

    def test_TC34_no_slot_for_reservation(self):
        """TC-34 Reservation fails when every slot of the type is taken"""
        db.park_vehicle(self.c, self.s, "AAA-111", "Car", "Ahmed Raza", "03001234567")
        db.park_vehicle(self.c, self.s, "BBB-222", "Car", "Ahmed Raza", "03001234567")
        with self.assertRaisesRegex(ParkingError, "No Car slot"): db.reserve_slot(self.c, self.u, self.v, 1)

    def test_TC35_expired_reservation_released(self):
        """TC-35 An expired reservation releases its slot automatically"""
        db.reserve_slot(self.c, self.u, self.v, 1)
        self.c.execute("UPDATE reservations SET end_time=?", (db.fmt(db.now() - timedelta(minutes=1)),)); self.c.commit()
        db.expire_reservations(self.c)
        self.assertEqual(db.reservations_list(self.c, self.u)[0]["status"], "Expired")
        self.assertEqual(db.free_slot_counts(self.c)["Car"], 2)

    def test_TC36_other_user_cannot_cancel(self):
        """TC-36 A user cannot cancel or reserve with another user's data"""
        other = db.register_user(self.c, "Sara Malik", "sara_m", "secret1", "03441112233")
        rid = db.reserve_slot(self.c, self.u, self.v, 1)["reservation_id"]
        with self.assertRaises(ParkingError): db.cancel_reservation(self.c, other, rid)
        with self.assertRaises(ParkingError): db.reserve_slot(self.c, other, self.v, 1)


class SlotTests(unittest.TestCase):
    def setUp(self): self.c, self.m, self.s, self.u = fresh()

    def test_TC37_add_and_validate_slot(self):
        """TC-37 Manager adds a slot; bad or duplicate numbers are rejected"""
        db.add_slot(self.c, self.m, "d4", "Car")
        for num, typ in (("D4", "Car"), ("44", "Car"), ("AB1", "Car"), ("E1", "Truck")):
            with self.assertRaises(ParkingError): db.add_slot(self.c, self.m, num, typ)

    def test_TC38_remove_slot_rules(self):
        """TC-38 Only an unused, available slot can be removed"""
        sid = self.c.execute("SELECT slot_id FROM slots WHERE slot_number='A2'").fetchone()[0]
        db.remove_slot(self.c, self.m, sid)
        db.park_vehicle(self.c, self.s, "LEA-101", "Car", "Ahmed Raza", "03001234567")
        busy = self.c.execute("SELECT slot_id FROM slots WHERE slot_number='A1'").fetchone()[0]
        with self.assertRaisesRegex(ParkingError, "available slot"): db.remove_slot(self.c, self.m, busy)

    def test_TC39_account_status(self):
        """TC-39 Manager disables and re-enables an account; disabled user cannot log in"""
        db.set_account_status(self.c, self.m, self.u, "Disabled")
        with self.assertRaisesRegex(ParkingError, "disabled"): db.authenticate(self.c, "aliuser", "user123", "User")
        db.set_account_status(self.c, self.m, self.u, "Active")
        self.assertEqual(db.authenticate(self.c, "aliuser", "user123", "User")["user_id"], self.u)
        with self.assertRaises(ParkingError): db.set_account_status(self.c, self.m, self.m, "Disabled")

    def test_TC41_slots_in_natural_order(self):
        """TC-41 Slots are listed and assigned in natural order (A2 before A10)"""
        for n in ("A3", "A10"):
            db.add_slot(self.c, self.m, n, "Car")
        order = [s["slot_number"] for s in db.slots_list(self.c) if s["slot_type"] == "Car"]
        self.assertEqual(order, ["A1", "A2", "A3", "A10"])
        for num in ("AAA-111", "BBB-222", "CCC-333", "DDD-444"):
            got = db.park_vehicle(self.c, self.s, num, "Car", "Ahmed Raza", "03001234567")["slot_number"]
            order.pop(0) if got == order[0] else self.fail(f"expected {order[0]} got {got}")

    def test_TC40_summary_matches_data(self):
        """TC-40 Dashboard summary equals the stored data"""
        db.park_vehicle(self.c, self.s, "LEA-101", "Car", "Ahmed Raza", "03001234567")
        db.exit_vehicle(self.c, self.s, "LEA-101", "Cash")
        db.park_vehicle(self.c, self.s, "LEB-202", "Bike", "Ahmed Raza", "03001234567")
        s = db.summary(self.c)
        self.assertEqual((s["total_slots"], s["occupied"], s["available"], s["revenue"]), (4, 1, 3, 100))


if __name__ == "__main__":
    unittest.main(verbosity=2)
