"""
Manager dashboard window (live KPI cards and charts).
Reads directly from the Smart Parking database through conn_factory().
"""
import calendar
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime


def open_dashboard(root, conn_factory, geometry="1320x820"):
    try:

        # ══════════════════════════════════════════════════════════
        #  DATABASE — live data
        # ══════════════════════════════════════════════════════════
        conn = conn_factory()
        total_slots = int(pd.read_sql("SELECT COUNT(*) as c FROM slots", conn)['c'][0])
        occupied = int(pd.read_sql("SELECT COUNT(*) as c FROM parking WHERE exit_time IS NULL", conn)['c'][0])
        available = total_slots - occupied
        revenue = float(pd.read_sql("SELECT IFNULL(SUM(amount),0) as r FROM payments", conn)['r'][0])
        vehicle_types = pd.read_sql(
            "SELECT vehicle_type || 's' AS Vehicle_Type, COUNT(*) as cnt FROM vehicles GROUP BY vehicle_type", conn)
        payment_types = pd.read_sql(
            "SELECT payment_method AS Payment_Method, COUNT(*) as cnt FROM payments GROUP BY payment_method", conn)
        monthly_rev = pd.read_sql("""
            SELECT CAST(strftime('%m', payment_date) AS INTEGER) as mnum, SUM(amount) as total
            FROM payments GROUP BY mnum ORDER BY mnum""", conn)
        monthly_rev['mon'] = [calendar.month_name[int(m)] for m in monthly_rev['mnum']]
        recent = pd.read_sql("""
            SELECT v.vehicle_number AS Vehicle_Number,
                   strftime('%H:%M:%S', p.entry_time) as entry,
                   s.slot_number AS Slot_Number
            FROM parking p
            JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            JOIN slots    s ON p.slot_id    = s.slot_id
            ORDER BY p.entry_time DESC LIMIT 5""", conn)
        hourly = pd.read_sql("""
            SELECT CAST(strftime('%H', entry_time) AS INTEGER) as hr, COUNT(*) as cnt
            FROM parking
            WHERE date(entry_time) = date('now', 'localtime')
            GROUP BY hr ORDER BY hr""", conn)
        conn.close()

        # ══════════════════════════════════════════════════════════
        #  COLOUR PALETTE
        # ══════════════════════════════════════════════════════════
        BG_DARK  = "#0a0f1e"
        BG_MID   = "#0d1530"
        BG_LIGHT = "#111d3c"
        GLASS    = "#131f3e"

        GRAD_BLUE   = "#1a4fd8"
        GRAD_GREEN  = "#0d7a5f"
        GRAD_ORANGE = "#b85c00"
        GRAD_PURPLE = "#5b2fa0"

        A_BLUE   = "#4d9fff"
        A_GREEN  = "#00e5a0"
        A_ORANGE = "#ff9d3d"
        A_PURPLE = "#b47aff"
        A_RED    = "#ff4d6d"

        BORDER = "#1e2e55"
        TEXT   = "#e8f0fe"
        MUTED  = "#7a90b8"
        DIM    = "#3a4f72"
        C_BG   = BG_MID

        # matplotlib global style
        plt.rcParams.update({
            'text.color':      TEXT,
            'axes.labelcolor': MUTED,
            'xtick.color':     MUTED,
            'ytick.color':     MUTED,
            'font.size':       8,
        })

        # ══════════════════════════════════════════════════════════
        #  WINDOW
        # ══════════════════════════════════════════════════════════
        win = tk.Toplevel(root)
        win.title("Smart Parking Dashboard")
        win.geometry(geometry)
        win.configure(bg=BG_DARK)
        win.resizable(True, True)

        # ══════════════════════════════════════════════════════════
        #  HEADER
        # ══════════════════════════════════════════════════════════
        header = tk.Frame(win, bg=BG_MID, height=62)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Left block
        left_h = tk.Frame(header, bg=BG_MID)
        left_h.pack(side="left", padx=20, fill="y")

        logo = tk.Frame(left_h, bg=A_BLUE, width=36, height=36)
        logo.pack(side="left", anchor="center", pady=13)
        logo.pack_propagate(False)
        tk.Label(logo, text="P", bg=A_BLUE, fg="white",
                 font=("Consolas", 14, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        title_blk = tk.Frame(left_h, bg=BG_MID)
        title_blk.pack(side="left", padx=(10, 0), anchor="center")
        tk.Label(title_blk, text="Smart Parking", bg=BG_MID, fg=A_BLUE,
                 font=("Arial", 13, "bold")).pack(anchor="w")
        tk.Label(title_blk, text=" Dashboard", bg=BG_MID, fg=MUTED,
                 font=("Arial", 8)).pack(anchor="w")

        # Right block
        right_h = tk.Frame(header, bg=BG_MID)
        right_h.pack(side="right", padx=20, fill="y")

        date_str = datetime.now().strftime("%d %B %Y")

        date_pill = tk.Frame(right_h, bg=BG_LIGHT)
        date_pill.pack(side="left", anchor="center", pady=17, padx=(0, 12))
        tk.Label(date_pill, text=f"  {date_str}  ",
                 bg=BG_LIGHT, fg=TEXT, font=("Arial", 9)).pack()

        tk.Frame(right_h, bg=BORDER, width=1, height=30).pack(
            side="left", anchor="center", pady=16, padx=4)

        admin_box = tk.Frame(right_h, bg=BG_MID)
        admin_box.pack(side="left", anchor="center", padx=(8, 0), pady=12)
        av = tk.Frame(admin_box, bg=A_PURPLE, width=34, height=34)
        av.pack(side="left")
        av.pack_propagate(False)
        tk.Label(av, text="A", bg=A_PURPLE, fg="white",
                 font=("Arial", 12, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        ai = tk.Frame(admin_box, bg=BG_MID)
        ai.pack(side="left", padx=(8, 0))
        tk.Label(ai, text="Admin",   bg=BG_MID, fg=TEXT,  font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(ai, text="Manager", bg=BG_MID, fg=MUTED, font=("Arial", 7)).pack(anchor="w")

        tk.Frame(win, bg=A_BLUE, height=3).pack(fill="x", side="top")

        # ══════════════════════════════════════════════════════════
        #  SCROLLABLE CONTENT
        # ══════════════════════════════════════════════════════════
        outer = tk.Frame(win, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        vbar = ttk.Scrollbar(outer, orient="vertical")
        vbar.pack(side="right", fill="y")

        mc = tk.Canvas(outer, bg=BG_DARK, highlightthickness=0,
                       yscrollcommand=vbar.set)
        mc.pack(side="left", fill="both", expand=True)
        vbar.config(command=mc.yview)

        content = tk.Frame(mc, bg=BG_DARK)
        cw = mc.create_window((0, 0), window=content, anchor="nw")

        content.bind("<Configure>",
                     lambda e: mc.configure(scrollregion=mc.bbox("all")))
        mc.bind("<Configure>",
                lambda e: mc.itemconfig(cw, width=e.width))
        win.bind("<MouseWheel>",
                 lambda e: mc.yview_scroll(int(-1*(e.delta/120)), "units"))

        PAD = 18

        # ── Section label ──
        def sec_lbl(parent, txt):
            r = tk.Frame(parent, bg=BG_DARK)
            r.pack(fill="x", padx=PAD, pady=(14, 4))
            tk.Label(r, text=txt, bg=BG_DARK, fg=MUTED,
                     font=("Arial", 8, "bold")).pack(side="left")
            tk.Frame(r, bg=BORDER, height=1).pack(
                side="left", fill="x", expand=True, padx=(10, 0), pady=7)

        # ══════════════════════════════════════════════════════════
        #  KPI CARDS
        # ══════════════════════════════════════════════════════════
        sec_lbl(content, "OVERVIEW")

        kpi_row = tk.Frame(content, bg=BG_DARK)
        kpi_row.pack(fill="x", padx=PAD, pady=(0, 6))

        kpi_data = [
            ("Total Slots",     str(total_slots),       GRAD_BLUE,   A_BLUE,   "P",  "All parking slots",  "+8% this week"),
            ("Available Slots", str(available),          GRAD_GREEN,  A_GREEN,  "OK", "Currently free",     "Open for parking"),
            ("Occupied Slots",  str(occupied),           GRAD_ORANGE, A_ORANGE, "!!", "Currently in use",   f"{int(occupied/max(total_slots,1)*100)}% full"),
            ("Today's Revenue", f"Rs {int(revenue):,}", GRAD_PURPLE, A_PURPLE, "$",  "Total collected",    "+18% vs yesterday"),
        ]

        for i, (title, value, base_bg, accent, icon, sub, badge) in enumerate(kpi_data):
            card = tk.Frame(kpi_row, bg=base_bg,
                            highlightbackground=accent,
                            highlightthickness=0,
                            cursor="hand2")
            card.pack(side="left", fill="both", expand=True,
                      padx=(0, 0) if i == 0 else (10, 0))

            # Top accent stripe
            tk.Frame(card, bg=accent, height=4).pack(fill="x")

            body = tk.Frame(card, bg=base_bg, padx=16, pady=12)
            body.pack(fill="both", expand=True)

            top_r = tk.Frame(body, bg=base_bg)
            top_r.pack(fill="x")

            # Icon circle
            ic = tk.Frame(top_r, bg=accent, width=42, height=42)
            ic.pack(side="left")
            ic.pack_propagate(False)
            tk.Label(ic, text=icon, bg=accent, fg="white",
                     font=("Consolas", 11, "bold")).place(
                         relx=0.5, rely=0.5, anchor="center")

            # Trend badge
            badge_lbl = tk.Label(top_r, text=badge,
                                 bg=base_bg, fg=accent,
                                 font=("Arial", 7, "bold"))
            badge_lbl.pack(side="right", anchor="n", padx=2)

            tk.Label(body, text=value,  bg=base_bg, fg="white",
                     font=("Arial", 22, "bold")).pack(anchor="w", pady=(8, 0))
            tk.Label(body, text=title,  bg=base_bg, fg="white",
                     font=("Arial", 10, "bold")).pack(anchor="w")
            tk.Label(body, text=sub,    bg=base_bg, fg=accent,
                     font=("Arial", 7)).pack(anchor="w")

            # Bottom accent stripe
            tk.Frame(card, bg=accent, height=1).pack(fill="x")

            # Hover glow
            for w in [card, body, top_r]:
                w.bind("<Enter>", lambda e, c=card, a=accent:
                       c.configure(highlightthickness=2, highlightbackground=a))
                w.bind("<Leave>", lambda e, c=card:
                       c.configure(highlightthickness=0))

        # ══════════════════════════════════════════════════════════
        #  MIDDLE ROW  — Line Chart + Donut
        # ══════════════════════════════════════════════════════════
        sec_lbl(content, "LIVE ANALYTICS")

        mid_row = tk.Frame(content, bg=BG_DARK)
        mid_row.pack(fill="x", padx=PAD, pady=(0, 6))

        def glass_panel(parent, title, sub, side="left", expand=True, fixed_w=None):
            outer = tk.Frame(parent, bg=GLASS,
                             highlightbackground=BORDER,
                             highlightthickness=1)
            outer.pack(side=side, fill="both", expand=expand,
                       padx=(0, 12) if side == "left" and expand else 0)
            if fixed_w:
                outer.configure(width=fixed_w)
                outer.pack_propagate(False)
            hdr = tk.Frame(outer, bg=BG_MID, padx=14, pady=10)
            hdr.pack(fill="x")
            tk.Label(hdr, text=title, bg=BG_MID, fg=TEXT,
                     font=("Arial", 10, "bold")).pack(side="left")
            if sub:
                tk.Label(hdr, text=sub, bg=BG_MID, fg=MUTED,
                         font=("Arial", 7)).pack(side="left", padx=(8, 0))
            inner = tk.Frame(outer, bg=GLASS, padx=8, pady=6)
            inner.pack(fill="both", expand=True)
            return inner

        # Line chart
        l_inner = glass_panel(mid_row,
                              "Parking Occupancy (Today)",
                              "Occupied slots per hour  (12 AM → 12 AM)",
                              side="left", expand=True)

        fig_l, ax_l = plt.subplots(figsize=(7.6, 2.9))
        fig_l.patch.set_facecolor(C_BG)
        ax_l.set_facecolor(C_BG)

      # Always create full 24 hours
        full_hours = list(range(24))

        if not hourly.empty:
             hour_dict = dict(zip(hourly['hr'], hourly['cnt']))
             hx = full_hours
             hy = [hour_dict.get(h, 0) for h in full_hours]
        else:
           hx = full_hours
           hy = [0]*24

        xlbls = []
        for h in hx:
            if h == 0:   xlbls.append("12 AM")
            elif h < 12: xlbls.append(f"{h} AM")
            elif h == 12:xlbls.append("12 PM")
            else:        xlbls.append(f"{h-12} PM")

        xp = np.arange(len(hx))
        ax_l.fill_between(xp, hy, alpha=0.20, color=A_BLUE)
        ax_l.fill_between(xp, hy, alpha=0.08, color=A_BLUE)
        ax_l.plot(xp, hy, color=A_BLUE, lw=2.8,
                  marker='o', ms=5,
                  markerfacecolor=BG_DARK,
                  markeredgecolor=A_BLUE, markeredgewidth=2,
                  zorder=5, solid_capstyle='round')

        ax_l.set_xticks(xp)
        ax_l.set_xticklabels(xlbls, fontsize=7.5, color=MUTED, rotation=30)
        ax_l.tick_params(axis='y', labelsize=7.5)
        ax_l.set_ylabel("Occupied Slots", fontsize=7.5, color=MUTED, labelpad=6)
        ax_l.grid(axis='y', color=BORDER, lw=0.7, ls='--', alpha=0.6)
        ax_l.grid(axis='x', color=BORDER, lw=0.4, ls=':', alpha=0.3)
        ax_l.set_xlim(-0.2, len(hx)-0.8)
        ax_l.set_ylim(0, max(hy)*1.3+1 if hy else 25)
        for s in ax_l.spines.values():
            s.set_edgecolor(BORDER); s.set_lw(0.8)
        fig_l.tight_layout(pad=0.8)

        cv_l = FigureCanvasTkAgg(fig_l, l_inner)
        cv_l.get_tk_widget().configure(bg=C_BG, highlightthickness=0)
        cv_l.get_tk_widget().pack(fill="both", expand=True)
        cv_l.draw()

        # Donut
        d_inner = glass_panel(mid_row,
                              "Slot Occupancy",
                              f"Total: {total_slots}",
                              side="left", expand=False, fixed_w=310)

        fig_d, ax_d = plt.subplots(figsize=(3.0, 2.9))
        fig_d.patch.set_facecolor(C_BG)
        ax_d.set_facecolor(C_BG)

        ax_d.pie([occupied, max(available, 0.001)],
                 colors=[A_RED, A_GREEN],
                 startangle=90, counterclock=False,
                 wedgeprops=dict(width=0.46, edgecolor=C_BG, linewidth=3))

        ax_d.text(0, 0.13, str(total_slots), ha='center', va='center',
                  fontsize=22, fontweight='bold', color=TEXT, fontfamily='monospace')
        ax_d.text(0, -0.16, "Total Slots", ha='center', va='center',
                  fontsize=8, color=MUTED)
        ax_d.legend(handles=[
            mpatches.Patch(color=A_GREEN, label=f'Available  {available}'),
            mpatches.Patch(color=A_RED,   label=f'Occupied   {occupied}'),
        ], loc='lower center', fontsize=8, frameon=False,
           labelcolor=TEXT, bbox_to_anchor=(0.5, -0.04), ncol=2,
           handlelength=1.2, handleheight=0.9)

        fig_d.tight_layout(pad=0.5)
        cv_d = FigureCanvasTkAgg(fig_d, d_inner)
        cv_d.get_tk_widget().configure(bg=C_BG, highlightthickness=0)
        cv_d.get_tk_widget().pack(fill="both", expand=True)
        cv_d.draw()

        # ══════════════════════════════════════════════════════════
        #  BOTTOM ROW — 4 panels
        # ══════════════════════════════════════════════════════════
        sec_lbl(content, "ANALYTICS & RECORDS")

        bot_row = tk.Frame(content, bg=BG_DARK)
        bot_row.pack(fill="x", padx=PAD, pady=(0, 16))

        def bot_panel(parent, title, sub, idx):
            outer = tk.Frame(parent, bg=GLASS,
                             highlightbackground=BORDER,
                             highlightthickness=1)
            outer.pack(side="left", fill="both", expand=True,
                       padx=(0, 12) if idx < 3 else 0)
            hdr = tk.Frame(outer, bg=BG_MID, padx=14, pady=9)
            hdr.pack(fill="x")
            tk.Label(hdr, text=title, bg=BG_MID, fg=TEXT,
                     font=("Arial", 9, "bold")).pack(side="left")
            if sub:
                tk.Label(hdr, text=sub, bg=BG_MID, fg=MUTED,
                         font=("Arial", 6)).pack(side="left", padx=(6, 0))
            inner = tk.Frame(outer, bg=GLASS, padx=4, pady=4)
            inner.pack(fill="both", expand=True)
            return inner

        def styled_bar_chart(inner, labels, vals, colors, size=(3.1, 2.5)):
            fig, ax = plt.subplots(figsize=size)
            fig.patch.set_facecolor(C_BG)
            ax.set_facecolor(C_BG)
            bars = ax.bar(labels, vals, color=colors, width=0.5,
                          linewidth=0, zorder=3)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x()+bar.get_width()/2,
                        bar.get_height() + max(vals)*0.025,
                        str(val) if max(vals) < 200 else
                        (f"{val/1000:.1f}K" if val >= 1000 else str(int(val))),
                        ha='center', va='bottom',
                        fontsize=8.5, color=TEXT, fontweight='bold')
            ax.set_ylim(0, max(vals)*1.3)
            ax.tick_params(axis='x', labelsize=8, colors=MUTED)
            ax.tick_params(axis='y', labelsize=7.5, colors=MUTED)
            ax.grid(axis='y', color=BORDER, lw=0.7, ls='--', alpha=0.6)
            if max(vals) >= 1000:
                ax.yaxis.set_major_formatter(
                    plt.FuncFormatter(lambda x, _:
                        f"{x/1000:.1f}K" if x >= 1000 else str(int(x))))
            for s in ax.spines.values():
                s.set_edgecolor(BORDER); s.set_lw(0.8)
            fig.tight_layout(pad=0.7)
            cv = FigureCanvasTkAgg(fig, inner)
            cv.get_tk_widget().configure(bg=C_BG, highlightthickness=0)
            cv.get_tk_widget().pack(fill="both", expand=True)
            cv.draw()
            return fig

        # 1. Vehicle Type Bar
        vi = bot_panel(bot_row, "Vehicle Type Analysis", "By category", 0)
        vt_key = 'cnt' if 'cnt' in vehicle_types.columns else 'count'
        fig_v = styled_bar_chart(
            vi,
            list(vehicle_types['Vehicle_Type']),
            list(vehicle_types[vt_key]),
            [A_BLUE, A_GREEN, A_PURPLE, A_ORANGE][:len(vehicle_types)])

        # 2. Monthly Revenue Bar
        mi = bot_panel(bot_row, "Monthly Revenue", "PKR / month", 1)
        mr_key = 'total' if 'total' in monthly_rev.columns else 'cnt'
        mon_vals = [float(x) for x in monthly_rev[mr_key]]
        mon_lbls = list(monthly_rev['mon'])
        rclrs = [A_BLUE]*(max(len(mon_lbls)-1, 0)) + [A_GREEN]
        fig_m = styled_bar_chart(mi, mon_lbls, mon_vals,
                                 rclrs[:len(mon_lbls)])

        # 3. Payment Method Donut
        pi = bot_panel(bot_row, "Payment Method", "Distribution", 2)
        pt_key = 'cnt' if 'cnt' in payment_types.columns else 'count'
        pay_vals  = [float(x) for x in payment_types[pt_key]]
        pay_lbls  = list(payment_types['Payment_Method'])
        pay_clrs  = [A_GREEN, A_BLUE, A_ORANGE][:len(pay_lbls)]

        fig_p, ax_p = plt.subplots(figsize=(3.1, 2.5))
        fig_p.patch.set_facecolor(C_BG)
        ax_p.set_facecolor(C_BG)
        wedges_p, texts_p, autos_p = ax_p.pie(
            pay_vals, labels=pay_lbls, colors=pay_clrs,
            autopct='%1.0f%%', startangle=90,
            wedgeprops=dict(edgecolor=C_BG, linewidth=2.5),
            textprops=dict(color=MUTED, fontsize=8),
            pctdistance=0.70, labeldistance=1.15)
        for at in autos_p:
            at.set_color(TEXT); at.set_fontsize(8.5); at.set_fontweight('bold')
        fig_p.tight_layout(pad=0.4)
        cv_p = FigureCanvasTkAgg(fig_p, pi)
        cv_p.get_tk_widget().configure(bg=C_BG, highlightthickness=0)
        cv_p.get_tk_widget().pack(fill="both", expand=True)
        cv_p.draw()

        # 4. Recent Entries Table
        ti = bot_panel(bot_row, "Recent Entries", "Latest records", 3)

        # Column headers
        hdr_r = tk.Frame(ti, bg=BG_LIGHT)
        hdr_r.pack(fill="x", pady=(2, 4))
        for col_name, col_w in [("Vehicle No", 13), ("Entry Time", 11), ("Slot No", 8)]:
            tk.Label(hdr_r, text=col_name, bg=BG_LIGHT, fg=MUTED,
                     font=("Arial", 7, "bold"),
                     width=col_w, anchor="w",
                     padx=6, pady=6).pack(side="left")

        tk.Frame(ti, bg=BORDER, height=1).pack(fill="x")

        for idx, row_d in recent.iterrows():
            row_bg = BG_LIGHT if idx % 2 == 0 else GLASS
            row_f  = tk.Frame(ti, bg=row_bg, cursor="hand2")
            row_f.pack(fill="x", pady=1)

            # Vehicle badge
         
            veh = str(row_d.get('Vehicle_Number', '---'))
            bf = tk.Frame(row_f, bg="#4d9fff")
            bf.pack(side="left", padx=(6, 0), pady=4)

            tk.Label(
              bf,
              text=veh,
              bg="#4d9fff",
              fg="white",          # better visibility
              font=("Consolas", 8, "bold"),
              width=11,
              anchor="w",
              padx=4
            ).pack()
 
            # Entry time
        # Entry time (FIXED)


            raw_time = row_d.get('entry', None)

            try:
                ent = pd.to_datetime(raw_time).strftime("%I:%M %p")  # 12-hour format
            except:
                ent = str(raw_time) if raw_time else "--:--"

            tk.Label(
            row_f,
            text=ent,
            bg=row_bg,
            fg=TEXT,
            font=("Arial", 8),
            width=11,
            anchor="w"
            ).pack(side="left", padx=4)

            # Slot pill
        
            slot = str(row_d.get('Slot_Number', '--'))
            sf = tk.Frame(row_f, bg="#00e5a0")
            sf.pack(side="left", padx=(4, 6), pady=4)

            tk.Label(
            sf,
            text=slot,
            bg="#00e5a0",
            fg="black",                 # better contrast
            font=("Arial", 8, "bold"),
            padx=8,                    # horizontal padding → pill shape
            pady=2                     # vertical padding
            ).pack()

            # Row hover
            def _ent(e, f=row_f, orig=row_bg):
                f.configure(bg=BORDER)
                for c in f.winfo_children():
                    try: c.configure(bg=BORDER)
                    except: pass
            def _lve(e, f=row_f, orig=row_bg):
                f.configure(bg=orig)
                for c in f.winfo_children():
                    try: c.configure(bg=orig)
                    except: pass
            row_f.bind("<Enter>", _ent)
            row_f.bind("<Leave>", _lve)

        # ══════════════════════════════════════════════════════════
        #  FOOTER
        # ══════════════════════════════════════════════════════════
        footer = tk.Frame(content, bg=BG_MID, height=34)
        footer.pack(fill="x", pady=(4, 0))
        footer.pack_propagate(False)
        now_s = datetime.now().strftime("%A, %d %B %Y  %H:%M")
        tk.Label(footer,
                 text=f"  SmartParking  System  |  {now_s}  |  Live Database",
                 bg=BG_MID, fg=DIM, font=("Arial", 7)).pack(side="left", pady=10)
        tk.Label(footer, text="v2.0  ", bg=BG_MID, fg=DIM,
                 font=("Arial", 7)).pack(side="right", pady=10)

        # ══════════════════════════════════════════════════════════
        #  CLEANUP ON CLOSE
        # ══════════════════════════════════════════════════════════
        def on_close():
            plt.close('all')
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

    except Exception as e:
        import traceback
        messagebox.showerror("Dashboard Error",
                             f"{str(e)}\n\n{traceback.format_exc()}")

