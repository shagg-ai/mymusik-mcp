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
        from tkinter import font, ttk
    except ImportError:
        raise bridge.BridgeError("Graphical setup needs Tk. Use mymusik-mcp pair in a terminal.") from None
    try:
        root = tk.Tk()
    except tk.TclError:
        raise bridge.BridgeError("Open setup in a desktop session or use mymusik-mcp pair in a terminal.") from None
    root.title("MyMusik Setup")
    style = ttk.Style(root)
    style.theme_use("clam")
    ink, muted, accent = "#241c2e", "#554b61", "#662cb0"
    paper, surface, header = "#f4f1f6", "#ffffff", "#21162e"
    root.configure(bg=paper)
    base = font.nametofont("TkDefaultFont").copy()
    base.configure(size=10)
    title = base.copy()
    title.configure(size=21, weight="bold")
    heading = base.copy()
    heading.configure(size=13, weight="bold")
    brand = base.copy()
    brand.configure(size=12, weight="bold")
    strong = base.copy()
    strong.configure(weight="bold")
    em = base.metrics("linespace")
    gap = max(6, em // 2)
    inset = 3 * gap

    def button_style(name, bg, fg, hover, pressed, border):
        style.configure(name, background=bg, foreground=fg, font=strong,
                        padding=(gap * 2, gap), borderwidth=1, relief="flat",
                        bordercolor=border, lightcolor=bg, darkcolor=bg, focuscolor=fg)
        style.map(name, background=[("disabled", "#e2dae8"), ("pressed", pressed), ("active", hover)],
                  foreground=[("disabled", muted)], bordercolor=[("focus", fg)])

    button_style("Pair.TButton", accent, "white", "#58229c", "#46197e", accent)
    button_style("Plain.TButton", surface, ink, "#f0eaf6", "#e3d8ed", "#cfc6d6")
    button_style("Link.TButton", surface, accent, "#f4eff9", "#e3d8ed", surface)
    style.configure("Link.TButton", padding=(gap, gap))

    def label(parent, text, bg=surface, fg=ink, face=base, **options):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=face, anchor="w",
                        justify="left", padx=0, pady=0, **options)

    # Use font-relative dimensions so platform text scaling also scales the layout.
    line_width = em * 29
    banner = tk.Frame(root, bg=header, padx=inset, pady=inset)
    banner.pack(fill="x")
    wordmark = tk.Frame(banner, bg=header)
    wordmark.pack(anchor="w")
    logo = tk.PhotoImage(file=str(Path(__file__).with_name("setup-icon.png")))
    root.iconphoto(True, logo)
    mark = logo.subsample(max(1, round(logo.width() / (em * 1.7))))
    tk.Label(wordmark, image=mark, bg=header, bd=0).pack(side="left", padx=(0, gap))
    label(wordmark, "MyMusik", header, "white", brand).pack(side="left")

    saved = Path(profile_path).is_file()
    hero = label(banner, "Connect your music player", header, "white", title)
    hero.pack(anchor="w", pady=(gap, 0))
    subtitle = label(banner, "A pairing profile is saved on this computer." if saved else
                     "Pair MyMusik with the MCP client on this computer.", header, "#dbd1e5")
    subtitle.pack(anchor="w", pady=(gap // 2, 0))

    card = tk.Frame(root, bg=surface, padx=inset, pady=inset,
                    highlightthickness=1, highlightbackground="#ded7e4")
    card.pack(fill="x", padx=inset, pady=(inset, gap))
    label(card, "Get an invitation", face=heading).pack(anchor="w")
    label(card, "Open MyMusik and go to Insights → Connect a device.", fg=muted,
          wraplength=line_width).pack(anchor="w", pady=(gap // 2, gap))
    launch = tk.Frame(card, bg=surface)
    launch.pack(anchor="w")

    def feedback(message, color="#922f3d"):
        status.configure(text=message, fg=color)
        status.pack(anchor="w", fill="x", pady=(gap, 0))

    def open_player():
        try:
            if os.name == "nt":
                os.startfile("mymusik://open")
            elif not webbrowser.open("mymusik://open"):
                raise OSError()
        except OSError:
            feedback("Open MyMusik from your apps, or choose Download MyMusik.")

    ttk.Button(launch, text="Open MyMusik", style="Plain.TButton", command=open_player).pack(side="left")
    ttk.Button(launch, text="Download MyMusik", style="Link.TButton",
               command=lambda: webbrowser.open("https://mymusik.app/en/download/")).pack(side="left", padx=gap)
    tk.Frame(card, bg="#e6dfea", height=1).pack(fill="x", pady=2 * gap)
    label(card, "Pair this computer", face=heading).pack(anchor="w")
    label(card, "Choose access and a duration using the shield. Select Apply, then Copy agent prompt.",
          fg=muted, wraplength=line_width).pack(anchor="w", pady=(gap // 2, gap))
    results = queue.Queue()


    def pair_in_background(text):
        try:
            connect(text, profile_path)
        except bridge.BridgeError as error:
            results.put((False, str(error)))
        except (ValueError, OSError, KeyError, TypeError):
            results.put((False, "Pairing could not finish. Check the profile location and copy a fresh invitation."))
        else:
            results.put((True, ""))

    def finish_pairing():
        try:
            success, message = results.get_nowait()
        except queue.Empty:
            root.after(100, finish_pairing)
            return
        pair_button.state(["!disabled"])
        pair_button.configure(text="Paste invitation and pair")
        if success:
            hero.configure(text="Your player is connected")
            subtitle.configure(text="Reconnect MyMusik in your MCP client, then ask it to list three albums.")
            config_button.configure(style="Pair.TButton")
            card.pack_forget()
            renew_button.pack(side="left", padx=gap)
            config_button.focus_set()
        else:
            feedback(message)

    def paste_and_pair():
        try:
            invitation = invitation_url(root.clipboard_get())
        except tk.TclError:
            feedback("The clipboard has no text. Choose Copy agent prompt in MyMusik first.")
            return
        except bridge.BridgeError as error:
            feedback(str(error))
            return
        pair_button.state(["disabled"])
        feedback("Connecting to MyMusik…", muted)
        pair_button.configure(text="Pairing…")
        threading.Thread(target=pair_in_background, args=(invitation,), daemon=True).start()
        root.after(100, finish_pairing)

    pair_button = ttk.Button(card, text="Paste invitation and pair", style="Pair.TButton", command=paste_and_pair)
    pair_button.pack(anchor="w", pady=(gap // 2, 0))
    status = label(card, "", wraplength=line_width)

    client = tk.Frame(root, bg=paper, padx=inset)
    client.pack(fill="x", pady=(gap, inset))
    label(client, "Client settings", paper, ink, heading).pack(anchor="w")
    client_hint = label(client, "Using a JSON configuration? Copy the MyMusik entry into mcpServers.",
                        paper, muted, wraplength=line_width)
    client_hint.pack(anchor="w", pady=(gap // 2, gap))

    def copy_config():
        try:
            root.clipboard_clear()
            root.clipboard_append(json.dumps(client_config(profile_path), indent=2))
        except tk.TclError:
            client_hint.configure(text="Clipboard unavailable. Run mymusik-mcp config to get the settings.")
        else:
            client_hint.configure(text="Configuration copied. Add the entry alongside your existing servers.")

    def show_pairing():
        card.pack(before=client, fill="x", padx=inset, pady=(inset, gap))
        renew_button.pack_forget()
        status.pack_forget()
        hero.configure(text="Pair this computer again")
        subtitle.configure(text="Copy a fresh invitation to renew or change access.")
        config_button.configure(style="Plain.TButton")
        pair_button.focus_set()

    client_actions = tk.Frame(client, bg=paper)
    client_actions.pack(anchor="w")
    config_button = ttk.Button(client_actions, text="Copy client configuration", command=copy_config,
                               style="Plain.TButton")
    config_button.pack(side="left")
    renew_button = ttk.Button(client_actions, text="Pair again", command=show_pairing, style="Plain.TButton")
    subtitle.configure(wraplength=line_width + inset)
    pair_button.focus_set()
    root.update_idletasks()
    root.minsize(root.winfo_reqwidth(), 1)
    root.resizable(True, False)
    root.mainloop()
