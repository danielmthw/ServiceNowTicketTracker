import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
import json
import os
import threading
import time
from datetime import datetime
import csv
import winsound
import sys
import requests
import tempfile
import subprocess


APP_NAME = "Ticket Tracker"
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), APP_NAME)

os.makedirs(APPDATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(APPDATA_DIR, "appdata.json")
SETTINGS_FILE = os.path.join(APPDATA_DIR, "settings.json")

STATES = ["New", "In Progress", "On Hold", "Resolved", "Cancelled"]


APP_VERSION = "1.0.0"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/danielmthw/ServiceNowTicketTracker/main/version.txt"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def auto_update():
    try:
        response = requests.get(VERSION_CHECK_URL, timeout=5, verify=False)
        latest_version = response.text.strip()

        if latest_version != APP_VERSION:
            download_url = f"https://github.com/danielmthw/ServiceNowTicketTracker/releases/download/v{latest_version}/TicketTracker.exe"

            if messagebox.askyesno("Update Available", f"A new version ({latest_version}) is available.\n\nDownload and install now?"):
                temp_dir = tempfile.gettempdir()
                exe_path = os.path.join(temp_dir, f"TicketTracker-{latest_version}.exe")

                with requests.get(download_url, stream=True) as r:
                    with open(exe_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                subprocess.Popen([exe_path], shell=True)
                messagebox.showinfo("Update Started", "The new version is launching.\nThis one will now close.")
                sys.exit()
        else:
            messagebox.showinfo("Up to Date", "You're already using the latest version.")

    except Exception as e:
        messagebox.showerror("Update Error", f"Failed to check for updates:\n{e}")


class TicketTrackerApp:
    def __init__(self, root):
        self.root = root
        root.iconbitmap(resource_path("sntt.ico"))
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x500")

        self.entries = []
        self.filtered_entries = []
        self.sort_column = None
        self.sort_reverse = False
        self.settings = self.load_settings()
        self.is_compact_view = False
        self.load_entries()

        self.create_widgets()
        if self.settings.get("default_view_mode", "Full") == "Compact":
            self.toggle_quick_entry_mode(force=True)
        self.root.bind("<Control-a>", self.select_all_rows)
        self.root.bind("<Delete>", self.delete_entries_shortcut)
        self.root.bind("<Shift-Up>", self.extend_selection_up)
        self.root.bind("<Shift-Down>", self.extend_selection_down)
        self.undo_stack = []
        self.root.bind("<Control-z>", self.undo_last_action)
        self.start_reminder_thread()
        self.start_autosave_thread()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {
            "reminders_enabled": True,
            "reminder_interval": 60,
            "default_view_mode": "Full"
        }

    def save_settings(self, settings):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    def open_settings(self):
        settings = self.settings

        win = tk.Toplevel(self.root)
        win.iconbitmap(resource_path("sntt.ico"))
        win.title("Settings")
        win.geometry("300x360")
        win.grab_set()

        reminders_enabled = tk.BooleanVar(value=settings.get("reminders_enabled", True))
        reminder_amount = tk.IntVar()
        reminder_unit = tk.StringVar()
        view_mode_var = tk.StringVar(value=settings.get("default_view_mode", "Full").capitalize())

        total_minutes = settings.get("reminder_interval", 60)
        if total_minutes % 60 == 0:
            reminder_amount.set(total_minutes // 60)
            reminder_unit.set("Hours")
        else:
            reminder_amount.set(total_minutes)
            reminder_unit.set("Minutes")

        reminder_frame = ttk.LabelFrame(win, text="Reminders", padding=10)
        reminder_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Checkbutton(reminder_frame, text="Enable Reminders", variable=reminders_enabled).pack(anchor="w", pady=(0, 5))

        ttk.Label(reminder_frame, text="Reminder Interval:").pack(anchor="w")
        interval_frame = ttk.Frame(reminder_frame)
        interval_frame.pack(anchor="w", pady=(0, 5))
        ttk.Entry(interval_frame, textvariable=reminder_amount, width=5).pack(side="left")
        ttk.Combobox(interval_frame, textvariable=reminder_unit, values=["Minutes", "Hours"], width=10, state="readonly").pack(side="left", padx=5)

        view_mode_frame = ttk.LabelFrame(win, text="Startup View", padding=10)
        view_mode_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(view_mode_frame, text="Default View Mode:").pack(anchor="w", pady=(0, 5))
        ttk.Combobox(view_mode_frame, textvariable=view_mode_var, values=["Full", "Compact"], state="readonly").pack(anchor="w")

        update_frame = ttk.LabelFrame(win, text="Updates", padding=5)
        update_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(update_frame, text="Check for Updates", command=auto_update).pack(anchor="w", pady=(0, 2))
        ttk.Label(update_frame, text=f"Current Version: v{APP_VERSION}", foreground="gray").pack(anchor="w", pady=(0, 5))


        button_frame = ttk.Frame(win)
        button_frame.pack(pady=(5, 10))


        def on_save():
            unit = reminder_unit.get()
            amount = max(1, reminder_amount.get())
            total = amount * 60 if unit == "Hours" else amount

            settings["reminders_enabled"] = reminders_enabled.get()
            settings["reminder_interval"] = min(1440, total)
            settings["default_view_mode"] = view_mode_var.get()

            self.save_settings(settings)
            self.settings = settings  # update the instance variable
            win.destroy()

        ttk.Button(button_frame, text="Save", command=on_save).pack(pady=5, fill="x")

    def start_reminder_thread(self):
        print("[DEBUG] Inside start_reminder_thread()")

        def remind_loop_safe():
            try:
                print("[Reminder Thread] Thread started.")
                while True:
                    try:
                        interval = self.settings.get("reminder_interval", 60)
                        print(f"[Reminder Thread] Sleeping for {interval} minutes...")
                        time.sleep(max(1, interval) * 60)
                        if self.settings.get("reminders_enabled", True):
                            print("[Reminder Thread] Triggering alert")
                            self.root.after(0, self.show_reminder)
                    except Exception as inner:
                        print(f"[Reminder Thread] Inner error: {inner}")
            except Exception as e:
                print(f"[Reminder Thread] Failed to start: {e}")

        try:
            print("[Reminder Thread] Launching thread...")
            thread = threading.Thread(target=remind_loop_safe, daemon=True)
            thread.start()
            print("[Reminder Thread] Successfully launched.")
        except Exception as e:
            print(f"[Reminder Thread] Fatal error: {e}")

    def show_reminder(self):
        pending = len([e for e in self.entries if not e.get("done")])
        if pending > 0:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            popup = tk.Toplevel(self.root)
            popup.title("Reminder")
            popup.geometry("250x100")
            popup.iconbitmap(resource_path("sntt.ico"))
            popup.update_idletasks()
            popup.attributes("-topmost", True)
            popup.lift()
            popup.focus_force()
            ttk.Label(popup, text=f"You have {pending} pending tickets to submit.", wraplength=300, justify="center").pack(pady=20)
            ttk.Button(popup, text="OK", command=popup.destroy).pack(pady=5)
    
    def create_widgets(self):
        self.create_form_section()
        self.create_search_section()
        self.create_treeview_section()
        self.create_status_bar()


    def create_form_section(self):
        form_frame = ttk.LabelFrame(self.root, text="New Entry", padding=5)
        form_frame.pack(padx=10, pady=1)

        content_frame = ttk.Frame(form_frame)
        content_frame.pack(fill=tk.X)

        content_frame.columnconfigure(0, weight=0)
        content_frame.columnconfigure(1, weight=0)
        content_frame.columnconfigure(2, weight=0)

        left_form = ttk.Frame(content_frame)
        left_form.grid(row=0, column=0, padx=10, sticky="nsew")

        right_form = ttk.Frame(content_frame)
        right_form.grid(row=0, column=1, padx=10, sticky="nsew")

        button_form = ttk.Frame(content_frame)
        button_form.grid(row=0, column=2, padx=10, sticky="nsew")

        form_font = ("Arial", 10)

        self.caller_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.additional_notes_var = tk.StringVar()
        self.assignment_group_var = tk.StringVar()
        self.state_var = tk.StringVar()
        self.search_var = tk.StringVar()

        ttk.Label(left_form, text="Caller", font=form_font).grid(row=0, column=0, sticky=tk.E, pady=2, padx=5)
        ttk.Entry(left_form, textvariable=self.caller_var, width=30, font=form_font).grid(row=0, column=1, pady=2)

        ttk.Label(left_form, text="Title*", font=form_font).grid(row=1, column=0, sticky=tk.E, pady=2, padx=5)
        ttk.Entry(left_form, textvariable=self.title_var, width=30, font=form_font).grid(row=1, column=1, pady=2)

        ttk.Label(left_form, text="Assignment Group", font=form_font).grid(row=2, column=0, sticky=tk.E, pady=2, padx=5)
        ttk.Entry(left_form, textvariable=self.assignment_group_var, width=30, font=form_font).grid(row=2, column=1, pady=2)

        ttk.Label(left_form, text="State", font=form_font).grid(row=3, column=0, sticky=tk.E, pady=2, padx=5)
        self.state_menu = ttk.Combobox(left_form, textvariable=self.state_var, values=STATES, state="readonly", width=28, font=form_font)
        self.state_menu.grid(row=3, column=1, pady=2)
        self.state_menu.set("New")

      
        ttk.Label(right_form, text="Description", font=form_font).grid(row=0, column=0, sticky=tk.E, pady=2, padx=5)

        desc_wrapper = ttk.Frame(right_form)
        desc_wrapper.grid(row=0, column=1, pady=5, sticky="ew")

        self.description_text = tk.Text(
            desc_wrapper,
            height=2,
            width=50,
            font=form_font,
            wrap="word",
            bd=0,
            relief="flat",
            background="white",
            foreground="black"
        )
        self.description_text.pack(side="top", fill="x")

        self.desc_underline = tk.Frame(desc_wrapper, height=2, bg="grey") 
        self.desc_underline.pack(fill="x")

        def on_desc_focus_in(event):
            self.desc_underline.config(bg="#1a73e8") 

        def on_desc_focus_out(event):
            self.desc_underline.config(bg="grey") 

        self.description_text.bind("<FocusIn>", on_desc_focus_in)
        self.description_text.bind("<FocusOut>", on_desc_focus_out)


        ttk.Label(right_form, text="Additional Notes", font=form_font).grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)

        notes_wrapper = ttk.Frame(right_form)
        notes_wrapper.grid(row=1, column=1, pady=5, sticky="ew")

        self.additional_notes_text = tk.Text(
            notes_wrapper,
            height=2,
            width=50,
            font=form_font,
            wrap="word",
            bd=0,
            relief="flat",
            background="white",
            foreground="black"
        )
        self.additional_notes_text.pack(side="top", fill="x")

        self.notes_underline = tk.Frame(notes_wrapper, height=2, bg="grey")
        self.notes_underline.pack(fill="x")

        def on_notes_focus_in(event):
            self.notes_underline.config(bg="#1a73e8")

        def on_notes_focus_out(event):
            self.notes_underline.config(bg="grey")

        self.additional_notes_text.bind("<FocusIn>", on_notes_focus_in)
        self.additional_notes_text.bind("<FocusOut>", on_notes_focus_out)


       
        add_btn = ttk.Button(button_form, text="    Add Ticket    ", command=self.add_entry)
        add_btn.grid(row=0, column=0, sticky="nsew", pady=2)

     
        self.view_mode_btn = ttk.Button(button_form, text="Compact View", command=self.toggle_quick_entry_mode)
        self.view_mode_btn.grid(row=1, column=0, sticky="nsew", pady=(10, 2))


        button_form.columnconfigure(1, weight=1)

    def create_search_section(self):
        search_frame = ttk.Frame(self.root)
        search_frame.pack(pady=10)

        combined_search_frame = ttk.Frame(search_frame)
        combined_search_frame.pack(side=tk.LEFT, padx=5)

        search_entry = ttk.Entry(combined_search_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT)

        search_entry.bind("<Return>", lambda event: self.search_entries())

        clear_btn = ttk.Button(
            combined_search_frame,
            text="✕",
            width=2,
            command=self.clear_search
        )
        clear_btn.pack(side=tk.LEFT, padx=(2, 2))

        ttk.Button(combined_search_frame, text="Search", command=self.search_entries).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="Export", command=self.export_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Edit", command=self.edit_entry_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Copy", command=self.copy_entry).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Delete", command=self.confirm_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Undo", command=self.undo_last_action).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=5)

     
        self.search_section = search_frame


    def create_treeview_section(self):
        self.treeview_container = ttk.Frame(self.root)
        self.treeview_container.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(self.treeview_container, padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree_scroll_y.grid(row=0, column=1, sticky="ns")

        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Done", "Timestamp", "Caller", "Title", "Description", "Additional Notes", "Assignment Group", "State"),
            show="headings",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        for col in self.tree["columns"]:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            if col == "Done":
                self.tree.column(col, width=40, anchor="center")
            elif col == "State":
                self.tree.column(col, width=70)
            else:
                self.tree.column(col, width=140)

        self.tree.bind("<Double-1>", self.edit_entry_window)
        self.tree.bind("<Button-1>", self.toggle_done)

        self.populate_tree(self.entries)


    def create_status_bar(self):
        self.status_var = tk.StringVar()

        self.status_bar_container = ttk.Frame(self.root)
        self.status_bar_container.pack(fill="x", side="bottom")

        separator = ttk.Separator(self.status_bar_container, orient="horizontal")
        separator.pack(fill="x", side="top")

        self.status_label = ttk.Label(self.status_bar_container, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x", side="bottom")

        self.update_status_bar()

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_status_bar())



    def update_status_bar(self):
        total = len(self.entries)
        selected = len(self.tree.selection())
        done = len([e for e in self.entries if e.get("done")])
        not_done = total - done
        timestamp = self.last_saved if hasattr(self, "last_saved") else "Not saved yet"

        self.status_var.set(
            f"● Total: {total}    ● Selected: {selected}    ● Submitted: {done}    ● Not Submitted: {not_done}    ● Last Saved: {timestamp}"
        )
    
    def select_all_rows(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def delete_entries_shortcut(self, event=None):
        self.confirm_delete()
        return "break"

    def extend_selection_up(self, event=None):
        current = self.tree.focus()
        prev = self.tree.prev(current)
        if prev:
            self.tree.selection_add(prev)
            self.tree.focus(prev)
            self.tree.see(prev)
        return "break"

    def extend_selection_down(self, event=None):
        current = self.tree.focus()
        next_item = self.tree.next(current)
        if next_item:
            self.tree.selection_add(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
        return "break"




    def confirm_delete(self):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected entries?"):
            self.delete_entries()

    def load_entries(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                try:
                    raw_entries = json.load(f)
                    self.entries = []
                    for e in raw_entries:
                        timestamp = e.get("timestamp", "")
                        try:
                            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                            timestamp = dt.strftime("%m/%d/%Y %I:%M:%S %p")
                        except:
                            pass
                        self.entries.append({
                            "timestamp": timestamp,
                            "caller": e.get("caller", ""),
                            "title": e.get("title", ""),
                            "description": e.get("description", ""),
                            "additional_notes": e.get("additional_notes", ""),
                            "assignment_group": e.get("assignment_group", ""),
                            "state": e.get("state", "New"),
                            "done": e.get("done", False)
                        })
                except json.JSONDecodeError:
                    self.entries = []

                
        def parse_time(entry):
            try:
                return datetime.strptime(entry["timestamp"], "%m/%d/%Y %I:%M:%S %p")
            except:
                return datetime.min

        self.entries.sort(key=parse_time, reverse=True)


    def save_entries(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.entries, f, indent=2)
        self.last_saved = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        self.update_status_bar()



    def clear_form(self):
        self.caller_var.set("")
        self.title_var.set("")
        self.description_text.delete("1.0", tk.END)
        self.additional_notes_text.delete("1.0", tk.END)
        self.assignment_group_var.set("")
        self.state_var.set("New")


    def add_entry(self):
        entry = {
            "timestamp": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
            "caller": self.caller_var.get(),
            "title": self.title_var.get(),
            "description": self.description_text.get("1.0", tk.END).strip(),
            "additional_notes": self.additional_notes_text.get("1.0", tk.END).strip(),
            "assignment_group": self.assignment_group_var.get(),
            "state": self.state_var.get(),
            "done": False
        }

        if not entry["title"]:
            messagebox.showerror("Error", "Enter a Title for Entry.")
            return

        self.entries.append(entry)

        # Explicitly sort entries by timestamp descending (newest first)
        self.entries.sort(key=lambda e: datetime.strptime(e["timestamp"], "%m/%d/%Y %I:%M:%S %p"), reverse=True)

        self.sort_column = "Timestamp"
        self.sort_reverse = True

        self.save_entries()
        self.populate_tree(self.entries, sort=False)
        self.update_status_bar()
        self.clear_form()

        # Select and scroll to the top row
        if self.tree.get_children():
            first_item = self.tree.get_children()[0]
            self.tree.selection_set(first_item)
            self.tree.focus(first_item)
            self.tree.yview_moveto(0)

        # Highlight green status bar for confirmation
        def show_confirmation():
            self.status_var.set("✔ New Ticket Added Successfully.")
            self.status_label.config(background="#d4edda", foreground="#155724")

            def reset_status():
                self.status_label.config(background="", foreground="black")
                self.update_status_bar()

            self.root.after(3000, reset_status)

        self.root.after(100, show_confirmation)



    def populate_tree(self, entries, sort=True):
        self.tree.delete(*self.tree.get_children())

        if sort:
            entries = sorted(entries, key=lambda e: datetime.strptime(e["timestamp"], "%m/%d/%Y %I:%M:%S %p"), reverse=True)

        for i, entry in enumerate(entries):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", tk.END, values=(
                "☑" if entry.get("done") else "☐",
                entry["timestamp"],
                entry["caller"],
                entry["title"],
                entry["description"],
                entry["additional_notes"],
                entry["assignment_group"],
                entry["state"]
            ), tags=(tag,))

        self.tree.tag_configure("evenrow", background="#dcdcdc")  
        self.tree.tag_configure("oddrow", background="white")




            

    def sort_by_column(self, col):
        self.sort_reverse = (self.sort_column == col and not self.sort_reverse)
        self.sort_column = col
        key = col.lower().replace(" ", "_")

        if col == "Done":
            def sort_key(entry):
                return entry.get("done", False)
        elif col == "Timestamp":
            def sort_key(entry):
                try:
                    return datetime.strptime(entry["timestamp"], "%m/%d/%Y %I:%M:%S %p")
                except:
                    return datetime.min
        else:
            def sort_key(entry):
                return entry.get(key, "").lower()

        sorted_data = sorted(self.entries, key=sort_key, reverse=self.sort_reverse)
        self.populate_tree(sorted_data, sort=False)



    def edit_entry_window(self, event=None):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        for item in selected_items:
            values = self.tree.item(item, "values")
            selected_timestamp = values[1]  

            for entry in self.entries:
                if entry["timestamp"] == selected_timestamp:
                    edit_win = tk.Toplevel(self.root)
                    edit_win.iconbitmap(resource_path("sntt.ico"))
                    edit_win.title("Edit Entry")
                    edit_win.geometry("500x330")
                    edit_win.grab_set()  

                    form_font = ("Arial", 10)
                    edit_fields = {}

                    fields = [
                        ("Caller", "caller"),
                        ("Title", "title"),
                        ("Description", "description"),
                        ("Additional Notes", "additional_notes"),
                        ("Assignment Group", "assignment_group"),
                        ("State", "state")
                    ]

                    row = 0
                    for label, key in fields:
                        ttk.Label(edit_win, text=label, font=form_font).grid(row=row, column=0, sticky="e", padx=5, pady=2)

                        if key in ["description", "additional_notes"]:
                            text_wrapper = ttk.Frame(edit_win)
                            text_wrapper.grid(row=row, column=1, padx=5, pady=2, sticky="ew")

                            text_widget = tk.Text(
                                text_wrapper,
                                height=4,
                                width=50,
                                font=form_font,
                                wrap="word",
                                bd=0,
                                relief="flat",
                                background="white",
                                foreground="black"
                            )
                            text_widget.insert(tk.END, entry[key])
                            text_widget.pack(side="top", fill="x")

                            underline = tk.Frame(text_wrapper, height=2, bg="grey")
                            underline.pack(fill="x")

                            def on_focus_in(event, u=underline): u.config(bg="#1a73e8")
                            def on_focus_out(event, u=underline): u.config(bg="grey")

                            text_widget.bind("<FocusIn>", on_focus_in)
                            text_widget.bind("<FocusOut>", on_focus_out)

                            edit_fields[key] = text_widget

                        elif key == "state":
                            state_var = tk.StringVar(value=entry[key])
                            combo = ttk.Combobox(edit_win, textvariable=state_var, values=STATES, state="readonly",
                                                font=form_font, width=48)
                            combo.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
                            edit_fields[key] = state_var

                        else:
                            var = tk.StringVar(value=entry[key])
                            entry_widget = ttk.Entry(edit_win, textvariable=var, width=50, font=form_font)
                            entry_widget.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
                            edit_fields[key] = var

                        row += 1

                  
                    done_var = tk.BooleanVar(value=entry.get("done", False))
                    done_check = ttk.Checkbutton(edit_win, text="Done", variable=done_var)
                    done_check.grid(row=row, column=1, sticky="w", padx=5, pady=(10, 5))
                    row += 1

                    
                    button_frame = ttk.Frame(edit_win)
                    button_frame.grid(row=row, column=0, columnspan=2, pady=15)

                    def save_changes():
                        for key in edit_fields:
                            if key in ["description", "additional_notes"]:
                                entry[key] = edit_fields[key].get("1.0", tk.END).strip()
                            else:
                                entry[key] = edit_fields[key].get()
                        entry["done"] = done_var.get()
                        self.save_entries()
                        self.populate_tree(self.entries)
                        edit_win.destroy()

                    def delete_entry():
                        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this entry?"):
                            self.entries.remove(entry)
                            self.undo_stack.append(("delete", [entry]))  
                            self.save_entries()
                            self.populate_tree(self.entries)
                            edit_win.destroy()

                           
                            def show_delete_confirmation():
                                self.status_var.set("✖ Ticket(s) Deleted Successfully.")
                                self.status_label.config(background="#f8d7da", foreground="#721c24")  

                                def reset_status():
                                    self.status_label.config(background="", foreground="black")
                                    self.update_status_bar()

                                self.root.after(3000, reset_status)

                            self.root.after(100, show_delete_confirmation)


                    ttk.Button(button_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="Delete", command=delete_entry).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="Cancel", command=edit_win.destroy).pack(side=tk.LEFT, padx=5)

                    break


    def toggle_quick_entry_mode(self, force=None):
        to_compact = not self.is_compact_view if force is None else force

        if to_compact:
            self.treeview_container.pack_forget()
            self.search_section.pack_forget()
            self.root.geometry("1000x160")
            self.view_mode_btn.config(text="Full View")
            self.is_compact_view = True
        else:
            self.search_section.pack(pady=10)
            self.treeview_container.pack(fill=tk.BOTH, expand=True)
            self.root.geometry("1000x500")
            self.view_mode_btn.config(text="Compact View")
            self.is_compact_view = False

        
        self.status_bar_container.pack_forget()
        self.status_bar_container.pack(fill="x", side="bottom")




    def copy_entry(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        values = self.tree.item(selected_item, "values")
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(f"{col}: {val}" for col, val in zip(self.tree["columns"], values)))
        self.root.update()

    def delete_entries(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        deleted = []
        for item in selected_items:
            values = self.tree.item(item, "values")
            timestamp = values[1]
            for e in self.entries:
                if e["timestamp"] == timestamp:
                    deleted.append(e)
                    break

        self.entries = [e for e in self.entries if e not in deleted]
        self.undo_stack.append(("delete", deleted))
        self.save_entries()
        self.populate_tree(self.entries)

        
        def show_delete_confirmation():
            self.status_var.set("✖ Ticket(s) Deleted Successfully.")
            self.status_label.config(background="#f8d7da", foreground="#721c24")  

            def reset_status():
                self.status_label.config(background="", foreground="black")
                self.update_status_bar()

            self.root.after(3000, reset_status)

        self.root.after(100, show_delete_confirmation)



    def undo_last_action(self, event=None):
        if not self.undo_stack:
            if event is None:  
                messagebox.showinfo("Undo", "No actions to undo.")
            return "break" if event else None

        action, data = self.undo_stack.pop()
        if action == "delete":
            self.entries.extend(data)
            self.entries.sort(key=lambda x: x["timestamp"])
            self.save_entries()
            self.populate_tree(self.entries)

            
            def show_undo_confirmation():
                self.status_var.set("⟲ Undo Successful.")
                self.status_label.config(background="#fff3cd", foreground="#856404")  

                def reset_status():
                    self.status_label.config(background="", foreground="black")
                    self.update_status_bar()

                self.root.after(3000, reset_status)

            self.root.after(100, show_undo_confirmation)

        return "break" if event else None




    def toggle_done(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if not row_id or col != "#1": 
            return

        values = self.tree.item(row_id, "values")
        timestamp = values[1]  

        for entry in self.entries:
            if entry["timestamp"] == timestamp:
                entry["done"] = not entry.get("done", False)
                break

        self.save_entries()
        self.populate_tree(self.entries)

    def search_entries(self):
        term = self.search_var.get().strip().lower()
        if not term:
            self.populate_tree(self.entries, sort=True)
            return

        def entry_matches(entry):
            for value in entry.values():
                if isinstance(value, bool):
                    val_str = "☑" if value else "☐"
                else:
                    val_str = str(value)
                if term in val_str.lower():
                    return True
            return False

        self.filtered_entries = [e for e in self.entries if entry_matches(e)]
        self.populate_tree(self.filtered_entries, sort=False)




    def clear_search(self):
        self.search_var.set("")
        self.populate_tree(self.entries, sort=True)
        self.update_status_bar()

    def export_to_csv(self):
        default_filename = f"Ticket_Export_{datetime.now().strftime('%Y-%m-%d_%I-%M-%S_%p')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filepath:
            return  

        with open(filepath, "w", newline="") as csvfile:
            fieldnames = ["timestamp", "caller", "title", "description", "additional_notes", "assignment_group", "state", "done"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry)

        messagebox.showinfo("Exported", f"Export Complete")

    def start_autosave_thread(self):
        def autosave_loop():
            while True:
                time.sleep(300)
                self.save_entries()

        threading.Thread(target=autosave_loop, daemon=True).start()

    def on_close(self):
        self.save_entries()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TicketTrackerApp(root)
    root.mainloop()
