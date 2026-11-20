"""
Smart Parking System - desktop application (Python / Tkinter).

Run:  python app.py
Screens: Home -> role login (Manager / Staff / User) -> role panel.
"""
import tkinter as tk
from tkinter import ttk

import parking_db as db
from dashboard import open_dashboard

# ------------------------------------------------------------------ theme
BG, BG2, CARD, FIELD, BORDER = "#0a0f1e", "#0d1530", "#131f3e", "#0a1230", "#1e2e55"
TEXT, MUTED, DARK = "#e8f0fe", "#7a90b8", "#06101f"
BLUE, GREEN, ORANGE, PURPLE, RED = "#4d9fff", "#00e5a0", "#ff9f43", "#a78bfa", "#ff5c7a"
ROLE_COLOR = {"Manager": PURPLE, "Staff": ORANGE, "User": GREEN}
STATUS_COLOR = {"Available": (GREEN, "#0b3a30"), "Occupied": (RED, "#43182a"), "Reserved": (ORANGE, "#43300f")}


def F(size, bold=False):
    return ("Arial", size, "bold" if bold else "normal")


def setup_style(root):
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", DARK)
    root.option_add("*TCombobox*Listbox.font", F(11))
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure("Dark.TCombobox", fieldbackground=FIELD, background=BORDER, foreground=TEXT, arrowcolor=BLUE,
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6, selectbackground=FIELD,
                 selectforeground=TEXT)
    st.map("Dark.TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])
    st.configure("Dark.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30,
                 borderwidth=0, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, font=F(10))
    st.configure("Dark.Treeview.Heading", background=BG2, foreground=BLUE, font=F(10, True), relief="flat", padding=6)
    st.map("Dark.Treeview", background=[("selected", BLUE)], foreground=[("selected", DARK)])
    st.map("Dark.Treeview.Heading", background=[("active", BG2)])
    st.configure("Vertical.TScrollbar", background=BORDER, troughcolor=CARD, bordercolor=CARD, arrowcolor=MUTED)


# -------------------------------------------------------------- widgets
def lighten(color, amount=28):
    c = color.lstrip("#")
    return "#" + "".join(f"{min(255, int(c[i:i + 2], 16) + amount):02x}" for i in (0, 2, 4))


def button(parent, text, command, color=BLUE, fg=DARK, padx=20, pady=9, font=None):
    b = tk.Button(parent, text=text, command=command, bg=color, fg=fg, activebackground=lighten(color),
                  activeforeground=fg, relief="flat", bd=0, cursor="hand2", font=font or F(10, True), padx=padx, pady=pady,
                  highlightthickness=0)
    b.bind("<Enter>", lambda e: b.config(bg=lighten(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


def card(parent, title=None, bg=CARD, width=None):
    f = tk.Frame(parent, bg=bg, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=18)
    if width:
        f.config(width=width)
        f.pack_propagate(False)
    if title:
        tk.Label(f, text=title, bg=bg, fg=TEXT, font=F(13, True)).pack(anchor="w", pady=(0, 12))
    return f


def labeled_entry(parent, label, show=None, value="", bg=CARD):
    box = tk.Frame(parent, bg=bg)
    box.pack(fill="x", pady=(0, 10))
    tk.Label(box, text=label, bg=bg, fg=MUTED, font=F(9)).pack(anchor="w", pady=(0, 3))
    border = tk.Frame(box, bg=BORDER, padx=1, pady=1)
    border.pack(fill="x")
    e = tk.Entry(border, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=F(11), show=show or "", width=32,
                 highlightthickness=0)
    e.pack(fill="x", ipady=7, padx=1)
    e.insert(0, value)
    e.bind("<FocusIn>", lambda ev: border.config(bg=BLUE))
    e.bind("<FocusOut>", lambda ev: border.config(bg=BORDER))
    return e


def labeled_combo(parent, label, values, bg=CARD, default=None):
    box = tk.Frame(parent, bg=bg)
    box.pack(fill="x", pady=(0, 10))
    tk.Label(box, text=label, bg=bg, fg=MUTED, font=F(9)).pack(anchor="w", pady=(0, 3))
    cb = ttk.Combobox(box, values=list(values), state="readonly", style="Dark.TCombobox", font=F(11))
    cb.pack(fill="x")
    if default is not None:
        cb.set(default)
    return cb


class Banner(tk.Label):
    """Inline success / error message shown inside a form."""

    def __init__(self, parent, bg=CARD, wrap=380):
        super().__init__(parent, text="", anchor="w", justify="left", font=F(10, True), wraplength=wrap, bg=bg)
        self.base = bg
        self.pack(fill="x", pady=(0, 6))

    def show(self, msg, ok=True):
        self.config(text=("✔  " if ok else "✖  ") + msg, bg="#0b3a30" if ok else "#47182a",
                    fg=GREEN if ok else RED, padx=12, pady=9)

    def clear(self):
        self.config(text="", bg=self.base, padx=0, pady=0)


def make_table(parent, columns, widths):
    wrap = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    tree = ttk.Treeview(wrap, columns=columns, show="headings", style="Dark.Treeview", selectmode="browse")
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("odd", background="#101a36")
    tree.tag_configure("even", background=CARD)
    wrap.tree = tree
    return wrap


def fill_table(tree, rows):
    tree.delete(*tree.get_children())
    for i, row in enumerate(rows):
        tree.insert("", "end", values=[("" if v is None else v) for v in row], tags=("odd" if i % 2 else "even",))


def stat_tile(parent, label, value, color):
    t = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=14)
    tk.Frame(t, bg=color, height=3).pack(fill="x", pady=(0, 10))
    v = tk.Label(t, text=str(value), bg=CARD, fg=color, font=F(24, True))
    v.pack(anchor="w")
    tk.Label(t, text=label, bg=CARD, fg=MUTED, font=F(9)).pack(anchor="w")
    t.value_label = v
    return t


def page_title(parent, title, subtitle=""):
    tk.Label(parent, text=title, bg=BG, fg=TEXT, font=F(20, True)).pack(anchor="w")
    if subtitle:
        tk.Label(parent, text=subtitle, bg=BG, fg=MUTED, font=F(10)).pack(anchor="w", pady=(2, 16))


# ------------------------------------------------------------------ panel shell
class Panel(tk.Frame):
    """Header + sidebar + content area shared by the three role panels."""

    def __init__(self, app, role, user, pages):
        super().__init__(app.container, bg=BG)
        self.app, self.role, self.user, self.pages = app, role, user, pages
        self.conn, self.uid = app.conn, user["user_id"]
        color = ROLE_COLOR[role]

        head = tk.Frame(self, bg=BG2, height=62)
        head.pack(fill="x")
        head.pack_propagate(False)
        logo = tk.Label(head, text="P", bg=BLUE, fg=DARK, font=F(16, True), width=2)
        logo.pack(side="left", padx=(22, 10), pady=12)
        tk.Label(head, text="Smart Parking System", bg=BG2, fg=TEXT, font=F(14, True)).pack(side="left")
        tk.Label(head, text=f" {role.upper()} ", bg=color, fg=DARK, font=F(8, True)).pack(side="left", padx=14)
        button(head, "Logout", app.show_home, color=BORDER, fg=TEXT, pady=6).pack(side="right", padx=22)
        tk.Label(head, text=user["full_name"], bg=BG2, fg=TEXT, font=F(10, True)).pack(side="right")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=BG2, width=230)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="MENU", bg=BG2, fg=MUTED, font=F(8, True)).pack(anchor="w", padx=24, pady=(22, 8))
        self.nav = []
        for i, (name, _) in enumerate(pages):
            b = tk.Button(side, text="   " + name, anchor="w", relief="flat", bd=0, cursor="hand2", bg=BG2, fg=MUTED,
                          activebackground=CARD, activeforeground=TEXT, font=F(10, True), padx=10, pady=11, highlightthickness=0,
                          command=lambda i=i: self.show(i))
            b.pack(fill="x", padx=12, pady=1)
            self.nav.append(b)
        self.content = tk.Frame(body, bg=BG, padx=30, pady=24)
        self.content.pack(side="left", fill="both", expand=True)
        self.color = color
        self.show(0)

    def show(self, index):
        for i, b in enumerate(self.nav):
            b.config(bg=CARD if i == index else BG2, fg=self.color if i == index else MUTED)
        for w in self.content.winfo_children():
            w.destroy()
        name, builder = self.pages[index]
        builder(self, self.content)

    # ----- pieces reused by several roles
    def availability_row(self, parent, bg=BG):
        row = tk.Frame(parent, bg=bg)
        tiles = {}
        for t, color in zip(db.VEHICLE_TYPES, (BLUE, GREEN, PURPLE)):
            tile = stat_tile(row, f"{t} slots free", 0, color)
            tile.pack(side="left", padx=(0, 12))
            tiles[t] = tile
        def refresh():
            for t, n in db.free_slot_counts(self.conn).items():
                tiles[t].value_label.config(text=str(n))
        refresh()
        row.refresh = refresh
        return row

    def page_slot_map(self, parent):
        page_title(parent, "Slot Map", "Live status of every parking slot")
        legend = tk.Frame(parent, bg=BG)
        legend.pack(anchor="w", pady=(0, 14))
        for status, (fg, bg) in STATUS_COLOR.items():
            tk.Label(legend, text=f"  {status}  ", bg=bg, fg=fg, font=F(9, True)).pack(side="left", padx=(0, 10))
        db.expire_reservations(self.conn)
        slots = db.slots_list(self.conn)
        for t in db.VEHICLE_TYPES:
            group = [s for s in slots if s["slot_type"] == t]
            box = card(parent, f"{t} parking")
            box.pack(fill="x", pady=(0, 12))
            grid = tk.Frame(box, bg=CARD)
            grid.pack(anchor="w")
            for i, s in enumerate(group):
                fg, bg = STATUS_COLOR[s["slot_status"]]
                tk.Label(grid, text=s["slot_number"], bg=bg, fg=fg, font=F(11, True), width=6, pady=12,
                         highlightbackground=fg, highlightthickness=1).grid(row=i // 10, column=i % 10, padx=4, pady=4)

    def searchable_table(self, parent, columns, widths, rows):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Search:", bg=BG, fg=MUTED, font=F(10)).pack(side="left")
        border = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        border.pack(side="left", padx=8)
        e = tk.Entry(border, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=F(10), width=28, highlightthickness=0)
        e.pack(ipady=5, padx=1)
        wrap = make_table(parent, columns, widths)
        wrap.pack(fill="both", expand=True)
        data = [tuple(r) for r in rows]
        def apply(_=None):
            q = e.get().strip().lower()
            fill_table(wrap.tree, [r for r in data if not q or q in " ".join(map(str, r)).lower()])
        e.bind("<KeyRelease>", apply)
        apply()
        return wrap.tree


# -------------------------------------------------------------- staff pages
def staff_park(p, parent):
    page_title(parent, "Park Vehicle", "Record a vehicle entry. A free slot of the right type is assigned automatically.")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x")
    form = card(row, "Vehicle Entry")
    form.pack(side="left", anchor="n", padx=(0, 20))
    banner = Banner(form)
    number = labeled_entry(form, "Vehicle Number (format ABC-123)")
    vtype = labeled_combo(form, "Vehicle Type", db.VEHICLE_TYPES, default="Car")
    owner = labeled_entry(form, "Owner Name")
    phone = labeled_entry(form, "Mobile Number (11 digits)")
    right = tk.Frame(row, bg=BG)
    right.pack(side="left", anchor="n")
    tk.Label(right, text="Availability right now", bg=BG, fg=MUTED, font=F(10, True)).pack(anchor="w", pady=(0, 8))
    avail = p.availability_row(right)
    avail.pack(anchor="w")

    def submit():
        try:
            r = db.park_vehicle(p.conn, p.uid, number.get(), vtype.get(), owner.get(), phone.get())
            note = " (reserved slot used)" if r["reserved"] else ""
            banner.show(f"Vehicle parked. Slot {r['slot_number']} assigned{note}.")
            for e in (number, owner, phone):
                e.delete(0, "end")
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
        avail.refresh()
    button(form, "Park Vehicle", submit, color=ORANGE).pack(fill="x", pady=(6, 0))


def staff_exit(p, parent):
    page_title(parent, "Exit & Payment", "Calculate the fee, collect payment and release the slot.")
    form = card(parent, "Vehicle Exit")
    form.pack(anchor="w")
    banner = Banner(form)
    number = labeled_entry(form, "Vehicle Number")
    info = tk.Label(form, text="", bg=CARD, fg=TEXT, font=F(10), justify="left", anchor="w")
    state = {"quoted": None}
    method = labeled_combo(form, "Payment Method", db.PAY_METHODS, default="Cash")

    def quote():
        try:
            q = db.quote_exit(p.conn, number.get())
            state["quoted"] = q["vehicle_number"]
            info.config(text=f"Slot: {q['slot_number']}\nEntry: {q['entry_time']}\nExit:  {q['exit_time']}\n"
                             f"Billed hours: {q['hours']}\nAmount due: Rs. {q['amount']}", fg=TEXT)
            banner.clear()
        except db.ParkingError as err:
            state["quoted"] = None
            info.config(text="")
            banner.show(str(err), ok=False)

    def pay():
        try:
            if state["quoted"] != number.get().strip().upper():
                raise db.ParkingError("Calculate the fee first.")
            q = db.exit_vehicle(p.conn, p.uid, number.get(), method.get())
            banner.show(f"Payment of Rs. {q['amount']} received. Slot {q['slot_number']} is now free.")
            info.config(text="")
            state["quoted"] = None
            number.delete(0, "end")
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(form, "Calculate Fee", quote, color=BLUE).pack(fill="x", pady=(2, 10))
    info.pack(fill="x", pady=(0, 10))
    button(form, "Collect Payment & Release Slot", pay, color=GREEN).pack(fill="x")


def staff_parked(p, parent):
    page_title(parent, "Parked Vehicles", "Vehicles currently inside the parking area")
    wrap = make_table(parent, ("Vehicle No.", "Type", "Owner", "Slot", "Entry Time"), (150, 90, 220, 90, 190))
    wrap.pack(fill="both", expand=True)
    fill_table(wrap.tree, [tuple(r) for r in db.active_parking(p.conn)])


def staff_reservations(p, parent):
    page_title(parent, "Reservations", "Slots held for users in advance")
    wrap = make_table(parent, ("ID", "Vehicle No.", "Slot", "From", "Until", "Status"), (60, 140, 80, 170, 170, 100))
    wrap.pack(fill="both", expand=True)
    fill_table(wrap.tree, [tuple(r) for r in db.reservations_list(p.conn)])


def all_records(p, parent):
    page_title(parent, "Parking Records", "Every entry and exit, newest first")
    p.searchable_table(parent, ("Record", "Vehicle No.", "Slot", "Entry Time", "Exit Time", "Amount (Rs.)"),
                       (80, 150, 80, 180, 180, 120), [tuple(r) for r in db.parking_records(p.conn)])


def all_slotmap(p, parent):
    p.page_slot_map(parent)


# ------------------------------------------------------------ manager pages
def mgr_home(p, parent):
    page_title(parent, "Manager Overview", "Today at a glance")
    s = db.summary(p.conn)
    row = tk.Frame(parent, bg=BG)
    row.pack(anchor="w", pady=(0, 18))
    for label, key, color in (("Total slots", "total_slots", BLUE), ("Occupied", "occupied", RED),
                              ("Available", "available", GREEN), ("Total revenue (Rs.)", "revenue", ORANGE)):
        stat_tile(row, label, f"{s[key]:,}", color).pack(side="left", padx=(0, 12))
    box = card(parent, "Analytics Dashboard")
    box.pack(anchor="w", fill="x")
    tk.Label(box, text="Open the full dashboard with live KPI cards, slot occupancy, revenue by month,\n"
                       "vehicle types, payment methods and recent entries.", bg=CARD, fg=MUTED, font=F(10),
             justify="left").pack(anchor="w", pady=(0, 12))
    button(box, "Open Dashboard", lambda: open_dashboard(p.app.root, p.app.new_conn), color=PURPLE).pack(anchor="w")


def mgr_accounts(p, parent):
    page_title(parent, "Accounts", "Create staff accounts and control access")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="both", expand=True)
    form = card(row, "New Staff Account")
    form.pack(side="left", anchor="n", padx=(0, 20))
    banner = Banner(form)
    name = labeled_entry(form, "Full Name")
    user = labeled_entry(form, "Username (4-20: a-z, 0-9, _)")
    pw = labeled_entry(form, "Password (min 6 characters)", show="•")
    phone = labeled_entry(form, "Mobile Number (11 digits)")
    right = tk.Frame(row, bg=BG)
    right.pack(side="left", fill="both", expand=True)
    wrap = make_table(right, ("ID", "Name", "Username", "Role", "Mobile", "Status"), (50, 160, 120, 80, 120, 80))
    wrap.pack(fill="both", expand=True)

    def load():
        fill_table(wrap.tree, [tuple(r) for r in db.accounts_list(p.conn)])
    def add():
        try:
            db.add_staff(p.conn, p.uid, name.get(), user.get(), pw.get(), phone.get())
            banner.show("Staff account created.")
            for e in (name, user, pw, phone):
                e.delete(0, "end")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    def toggle(status):
        sel = wrap.tree.selection()
        if not sel:
            banner.show("Select an account in the table first.", ok=False)
            return
        try:
            db.set_account_status(p.conn, p.uid, int(wrap.tree.item(sel[0])["values"][0]), status)
            banner.show(f"Account set to {status}.")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(form, "Create Staff Account", add, color=PURPLE).pack(fill="x", pady=(4, 0))
    bar = tk.Frame(right, bg=BG)
    bar.pack(fill="x", pady=(10, 0))
    button(bar, "Enable / Unlock Selected", lambda: toggle("Active"), color=GREEN).pack(side="left", padx=(0, 10))
    button(bar, "Disable Selected", lambda: toggle("Disabled"), color=RED, fg=TEXT).pack(side="left")
    load()


def mgr_slots(p, parent):
    page_title(parent, "Slot Management", "Add or remove parking slots")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="both", expand=True)
    form = card(row, "Add Slot")
    form.pack(side="left", anchor="n", padx=(0, 20))
    banner = Banner(form)
    number = labeled_entry(form, "Slot Number (e.g. A11)")
    stype = labeled_combo(form, "Slot Type", db.VEHICLE_TYPES, default="Car")
    right = tk.Frame(row, bg=BG)
    right.pack(side="left", fill="both", expand=True)
    wrap = make_table(right, ("ID", "Slot", "Type", "Status"), (60, 120, 120, 120))
    wrap.pack(fill="both", expand=True)

    def load():
        fill_table(wrap.tree, [(s["slot_id"], s["slot_number"], s["slot_type"], s["slot_status"]) for s in db.slots_list(p.conn)])
    def add():
        try:
            db.add_slot(p.conn, p.uid, number.get(), stype.get())
            banner.show("Slot added.")
            number.delete(0, "end")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    def remove():
        sel = wrap.tree.selection()
        if not sel:
            banner.show("Select a slot in the table first.", ok=False)
            return
        try:
            db.remove_slot(p.conn, p.uid, int(wrap.tree.item(sel[0])["values"][0]))
            banner.show("Slot removed.")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(form, "Add Slot", add, color=PURPLE).pack(fill="x", pady=(4, 0))
    button(right, "Remove Selected Slot", remove, color=RED, fg=TEXT).pack(anchor="w", pady=(10, 0))
    load()


def mgr_tariff(p, parent):
    page_title(parent, "Tariff Settings", "Hourly rate per vehicle type (charged per started hour, minimum one hour)")
    box = card(parent, "Hourly Rates (Rs.)")
    box.pack(anchor="w")
    banner = Banner(box)
    entries = {}
    for r in db.rates_list(p.conn):
        entries[r["vehicle_type"]] = labeled_entry(box, f"{r['vehicle_type']} - rate per hour", value=str(r["hourly_rate"]))
    def save():
        try:
            for t, e in entries.items():
                db.set_rate(p.conn, p.uid, t, e.get())
            banner.show("Tariff updated.")
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(box, "Save Tariff", save, color=PURPLE).pack(fill="x", pady=(4, 0))


def mgr_payments(p, parent):
    page_title(parent, "Payments", "All collected payments, newest first")
    p.searchable_table(parent, ("Payment", "Vehicle No.", "Amount (Rs.)", "Date", "Method"), (90, 160, 130, 130, 120),
                       [tuple(r) for r in db.payments_list(p.conn)])


# --------------------------------------------------------------- user pages
def user_vehicles(p, parent):
    page_title(parent, "My Vehicles", "Register your vehicles to reserve slots")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="both", expand=True)
    form = card(row, "Add Vehicle")
    form.pack(side="left", anchor="n", padx=(0, 20))
    banner = Banner(form)
    number = labeled_entry(form, "Vehicle Number (format ABC-123)")
    vtype = labeled_combo(form, "Vehicle Type", db.VEHICLE_TYPES, default="Car")
    owner = labeled_entry(form, "Owner Name", value=p.user["full_name"])
    phone = labeled_entry(form, "Mobile Number (11 digits)", value=p.user["phone"] or "")
    wrap = make_table(row, ("Vehicle No.", "Type", "Owner", "Mobile"), (140, 90, 200, 140))
    wrap.pack(side="left", fill="both", expand=True)

    def load():
        fill_table(wrap.tree, [(v["vehicle_number"], v["vehicle_type"], v["owner_name"], v["phone"])
                               for v in db.user_vehicles(p.conn, p.uid)])
    def add():
        try:
            db.add_vehicle(p.conn, p.uid, number.get(), vtype.get(), owner.get(), phone.get())
            banner.show("Vehicle registered.")
            number.delete(0, "end")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(form, "Add Vehicle", add, color=GREEN).pack(fill="x", pady=(4, 0))
    load()


def user_reserve(p, parent):
    page_title(parent, "Reserve a Slot", "Hold a slot for your vehicle before you arrive")
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x")
    form = card(row, "New Reservation")
    form.pack(side="left", anchor="n", padx=(0, 20))
    banner = Banner(form)
    vehicles = db.user_vehicles(p.conn, p.uid)
    choices = [f"{v['vehicle_number']}  ({v['vehicle_type']})" for v in vehicles]
    vcombo = labeled_combo(form, "Vehicle", choices, default=choices[0] if choices else None)
    hours = labeled_combo(form, "Duration (hours)", [str(h) for h in range(1, db.MAX_RESERVE_HOURS + 1)], default="2")
    right = tk.Frame(row, bg=BG)
    right.pack(side="left", anchor="n")
    tk.Label(right, text="Availability right now", bg=BG, fg=MUTED, font=F(10, True)).pack(anchor="w", pady=(0, 8))
    avail = p.availability_row(right)
    avail.pack(anchor="w")

    def reserve():
        try:
            if not vehicles:
                raise db.ParkingError("Register a vehicle first.")
            v = vehicles[choices.index(vcombo.get())]
            r = db.reserve_slot(p.conn, p.uid, v["vehicle_id"], hours.get())
            banner.show(f"Slot {r['slot_number']} reserved for {hours.get()} hour(s). Show your vehicle number at the gate.")
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
        avail.refresh()
    button(form, "Reserve Slot", reserve, color=GREEN).pack(fill="x", pady=(4, 0))


def user_reservations(p, parent):
    page_title(parent, "My Reservations", "Active and past reservations")
    banner = Banner(parent, bg=BG, wrap=700)
    wrap = make_table(parent, ("ID", "Vehicle No.", "Slot", "From", "Until", "Status"), (60, 140, 80, 170, 170, 100))
    wrap.pack(fill="both", expand=True)

    def load():
        fill_table(wrap.tree, [tuple(r) for r in db.reservations_list(p.conn, user_id=p.uid)])
    def cancel():
        sel = wrap.tree.selection()
        if not sel:
            banner.show("Select a reservation first.", ok=False)
            return
        try:
            db.cancel_reservation(p.conn, p.uid, int(wrap.tree.item(sel[0])["values"][0]))
            banner.show("Reservation cancelled. The slot is free again.")
            load()
        except db.ParkingError as err:
            banner.show(str(err), ok=False)
    button(parent, "Cancel Selected Reservation", cancel, color=RED, fg=TEXT).pack(anchor="w", pady=(10, 0))
    load()


def user_history(p, parent):
    page_title(parent, "Parking History", "Your past and current parking sessions")
    wrap = make_table(parent, ("Record", "Vehicle No.", "Slot", "Entry Time", "Exit Time", "Amount (Rs.)"),
                      (80, 150, 80, 180, 180, 120))
    wrap.pack(fill="both", expand=True)
    fill_table(wrap.tree, [tuple(r) for r in db.parking_records(p.conn, user_id=p.uid)])


STAFF_PAGES = [("Park Vehicle", staff_park), ("Exit & Payment", staff_exit), ("Parked Vehicles", staff_parked),
               ("Reservations", staff_reservations), ("Slot Map", all_slotmap), ("Parking Records", all_records)]
MANAGER_PAGES = [("Overview", mgr_home), ("Accounts", mgr_accounts), ("Slot Management", mgr_slots),
                 ("Tariff Settings", mgr_tariff), ("Parking Records", all_records), ("Payments", mgr_payments),
                 ("Reservations", staff_reservations), ("Slot Map", all_slotmap)]
USER_PAGES = [("My Vehicles", user_vehicles), ("Reserve a Slot", user_reserve), ("My Reservations", user_reservations),
              ("Parking History", user_history), ("Slot Map", all_slotmap)]
PAGES = {"Manager": MANAGER_PAGES, "Staff": STAFF_PAGES, "User": USER_PAGES}


# ------------------------------------------------------------------ app shell
class App:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.conn = db.open_database(db_path)
        self.root = tk.Tk()
        self.root.title("Smart Parking System")
        self.root.configure(bg=BG)
        w, h = 1280, 780
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(1100, 680)
        setup_style(self.root)
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.show_home()

    def new_conn(self):
        return db.connect(self.db_path)

    def _swap(self, frame_builder):
        for w in self.container.winfo_children():
            w.destroy()
        frame = frame_builder()
        frame.pack(fill="both", expand=True)
        return frame

    # ---- home
    def show_home(self):
        self._swap(self._home_frame)

    def _home_frame(self):
        f = tk.Frame(self.container, bg=BG)
        top = tk.Frame(f, bg=BG)
        top.pack(fill="x", padx=50, pady=(30, 0))
        tk.Label(top, text="P", bg=BLUE, fg=DARK, font=F(18, True), width=2).pack(side="left")
        tk.Label(top, text="  Smart Parking System", bg=BG, fg=TEXT, font=F(16, True)).pack(side="left")
        tk.Label(f, text="Park smarter. Manage easier.", bg=BG, fg=TEXT, font=F(30, True)).pack(pady=(60, 6))
        tk.Label(f, text="Reserve slots, record entries and exits, collect payments and monitor the parking area from one place.",
                 bg=BG, fg=MUTED, font=F(12)).pack()
        tk.Label(f, text="Choose how you want to sign in", bg=BG, fg=BLUE, font=F(11, True)).pack(pady=(34, 18))
        row = tk.Frame(f, bg=BG)
        row.pack()
        info = {
            "Manager": ("M", "Control staff, slots and tariff.\nView the analytics dashboard\nand all reports."),
            "Staff": ("S", "Record vehicle entry and exit.\nCalculate fees and collect\npayments at the gate."),
            "User": ("U", "Register your vehicles.\nReserve a parking slot and\nview your parking history."),
        }
        for role, (letter, desc) in info.items():
            color = ROLE_COLOR[role]
            c = tk.Frame(row, bg=CARD, highlightbackground=BORDER, highlightthickness=1, width=300, height=290)
            c.pack(side="left", padx=14)
            c.pack_propagate(False)
            tk.Frame(c, bg=color, height=4).pack(fill="x")
            tk.Label(c, text=letter, bg=color, fg=DARK, font=F(20, True), width=3, pady=4).pack(pady=(24, 12))
            tk.Label(c, text=role, bg=CARD, fg=TEXT, font=F(16, True)).pack()
            tk.Label(c, text=desc, bg=CARD, fg=MUTED, font=F(10), justify="center").pack(pady=(8, 16))
            button(c, f"{role} Login", lambda r=role: self.show_login(r), color=color, padx=40).pack()
        tk.Label(f, text="Software Engineering (CT-365)  |  Complex Computing Problem", bg=BG, fg=MUTED,
                 font=F(9)).pack(side="bottom", pady=16)
        return f

    # ---- login
    def show_login(self, role):
        self._swap(lambda: self._login_frame(role))

    def _login_frame(self, role):
        color = ROLE_COLOR[role]
        f = tk.Frame(self.container, bg=BG)
        box = tk.Frame(f, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=36, pady=28)
        box.place(relx=0.5, rely=0.5, anchor="center")
        tk.Frame(box, bg=color, height=4).pack(fill="x", pady=(0, 20))
        tk.Label(box, text=f"{role} Login", bg=CARD, fg=TEXT, font=F(20, True)).pack(anchor="w")
        tk.Label(box, text="Enter your credentials to continue", bg=CARD, fg=MUTED, font=F(10)).pack(anchor="w", pady=(2, 18))
        banner = Banner(box)
        user = labeled_entry(box, "Username")
        pw = labeled_entry(box, "Password", show="•")

        def go(_=None):
            try:
                row = db.authenticate(self.conn, user.get(), pw.get(), role)
                self._swap(lambda: Panel(self, role, row, PAGES[role]))
            except db.ParkingError as err:
                banner.show(str(err), ok=False)
        pw.bind("<Return>", go)
        user.bind("<Return>", lambda e: pw.focus_set())
        button(box, "Sign In", go, color=color).pack(fill="x", pady=(6, 8))
        if role == "User":
            button(box, "Create a new account", self.show_register, color=CARD, fg=GREEN).pack(fill="x")
        button(box, "← Back to Home", self.show_home, color=CARD, fg=MUTED).pack(fill="x")
        user.focus_set()
        return f

    # ---- registration
    def show_register(self):
        self._swap(self._register_frame)

    def _register_frame(self):
        f = tk.Frame(self.container, bg=BG)
        box = tk.Frame(f, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=36, pady=24)
        box.place(relx=0.5, rely=0.5, anchor="center")
        tk.Frame(box, bg=GREEN, height=4).pack(fill="x", pady=(0, 16))
        tk.Label(box, text="Create User Account", bg=CARD, fg=TEXT, font=F(20, True)).pack(anchor="w", pady=(0, 12))
        banner = Banner(box)
        name = labeled_entry(box, "Full Name")
        user = labeled_entry(box, "Username (4-20: a-z, 0-9, _)")
        pw = labeled_entry(box, "Password (min 6 characters)", show="•")
        pw2 = labeled_entry(box, "Confirm Password", show="•")
        phone = labeled_entry(box, "Mobile Number (11 digits)")

        def register():
            try:
                if pw.get() != pw2.get():
                    raise db.ParkingError("Passwords do not match.")
                db.register_user(self.conn, name.get(), user.get(), pw.get(), phone.get())
                banner.show("Account created. You can sign in now.")
                for e in (name, user, pw, pw2, phone):
                    e.delete(0, "end")
            except db.ParkingError as err:
                banner.show(str(err), ok=False)
        button(box, "Register", register, color=GREEN).pack(fill="x", pady=(4, 8))
        button(box, "← Back to User Login", lambda: self.show_login("User"), color=CARD, fg=MUTED).pack(fill="x")
        return f

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
