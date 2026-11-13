"""Local desktop pairing. Import Tk only when the user opens setup."""

import json
import os
from pathlib import Path
import queue
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlsplit

if __package__:
    from . import mcp_stdio as bridge
else:
    import mcp_stdio as bridge


def invitation_url(text):
    if len(text) > bridge.MAX_MESSAGE:
        raise bridge.BridgeError("The copied text is too long. Copy a fresh MyMusik invitation.")
    # In the app's copied prompt the invitation occupies its own line.
    urls = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("https://", "http://")) and not any(c.isspace() for c in line):
            try:
                if "grant" in parse_qs(urlsplit(line).fragment, keep_blank_values=True):
                    urls.add(line)
            except ValueError:
                continue
    if len(urls) != 1:
        raise bridge.BridgeError("Copy one invitation using Copy agent prompt in MyMusik, then try again.")
    return urls.pop()


def connect(text, profile_path):
    profile, hello = bridge.pair(invitation_url(text))
    bridge.save_profile(profile_path, profile)
    return hello


def client_config(profile_path):
    executable = Path(sys.executable)
    if os.name == "nt" and executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    args = [str(Path(__file__).resolve().with_name("cli.py")), "stdio",
            "--profile", str(Path(profile_path).absolute())]
    return {"mcpServers": {"mymusik": {"command": str(executable), "args": args}}}


def open_setup(profile_path):
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        raise bridge.BridgeError("Graphical setup needs Tk. Use mymusik-mcp pair in a terminal.") from None
    try:
        root = tk.Tk()
    except tk.TclError:
        raise bridge.BridgeError("Open setup in a desktop session or use mymusik-mcp pair in a terminal.") from None
    root.title("Connect MyMusik")
    frame = ttk.Frame(root, padding=20)
    frame.grid(sticky="nsew")
    root.columnconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    width = 440

    def label(text, row, **style):
        widget = ttk.Label(frame, text=text, wraplength=width, justify="left", **style)
        widget.grid(row=row, column=0, sticky="w", pady=(0, 8))
        return widget

    from tkinter import font
    heading_font = font.nametofont("TkDefaultFont").copy()
    heading_font.configure(size=12, weight="bold")
    label("Open your music player", 0, font=heading_font)
    launch = ttk.Frame(frame)
    launch.grid(row=1, column=0, sticky="w", pady=(0, 12))

    def open_player():
        try:
            if os.name == "nt":
                os.startfile("mymusik://open")
            elif not webbrowser.open("mymusik://open"):
                raise OSError()
        except OSError:
            status.configure(text="Open MyMusik from your apps, or choose Download MyMusik.")

    ttk.Button(launch, text="Open MyMusik", command=open_player).pack(side="left")
    ttk.Button(launch, text="Download MyMusik",
               command=lambda: webbrowser.open("https://mymusik.app/en/download/")).pack(side="left", padx=6)
    label("Pair this computer", 2, font=heading_font)
    label("In MyMusik, open Insights → Connect a device. Use the shield to choose access and a duration, "
          "then choose Apply → Copy agent prompt.", 3)
    results = queue.Queue()

    def pair_in_background(text):
        try:
            connect(text, profile_path)
        except bridge.BridgeError as error:
            results.put((False, str(error)))
        except (ValueError, OSError, KeyError, TypeError):
            results.put((False, "Pairing could not finish. Check the profile location and copy a fresh invitation."))
        else:
            results.put((True, "Connected. Add the configuration to your MCP client or reconnect its MyMusik entry. "
                               "Then ask it to list three albums."))

    def finish_pairing():
        try:
            success, message = results.get_nowait()
        except queue.Empty:
            root.after(100, finish_pairing)
            return
        pair_button.state(["!disabled"])
        status.configure(text=message)
        if success:
            config_button.focus_set()

    def paste_and_pair():
        try:
            invitation = invitation_url(root.clipboard_get())
        except tk.TclError:
            status.configure(text="The clipboard has no text. Choose Copy agent prompt in MyMusik first.")
            return
        except bridge.BridgeError as error:
            status.configure(text=str(error))
            return
        pair_button.state(["disabled"])
        status.configure(text="Connecting to MyMusik…")
        threading.Thread(target=pair_in_background, args=(invitation,), daemon=True).start()
        root.after(100, finish_pairing)

    pair_button = ttk.Button(frame, text="Paste invitation and pair", command=paste_and_pair)
    pair_button.grid(row=4, sticky="w", pady=(0, 12))
    label("Connect your MCP client", 5, font=heading_font)
    label("If you installed the MyMusik plugin, reconnect it after pairing. If your client uses an "
          "mcpServers configuration, copy the settings here.", 6)

    def copy_config():
        root.clipboard_clear()
        root.clipboard_append(json.dumps(client_config(profile_path), indent=2))
        status.configure(text="Configuration copied. Add the mymusik entry alongside your existing servers.")

    config_button = ttk.Button(frame, text="Copy client configuration", command=copy_config)
    config_button.grid(row=7, sticky="w", pady=(0, 12))
    status = label("A saved connection exists. Pair again to renew or change access."
                   if Path(profile_path).is_file() else "", 8)
    pair_button.focus_set()
    root.update_idletasks()
    root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
    root.mainloop()
