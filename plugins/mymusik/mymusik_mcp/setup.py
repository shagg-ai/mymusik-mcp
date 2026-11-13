"""Local desktop pairing. Import Tk only when the user opens setup."""

import json
import math
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


FIRST_PROMPT = "List three albums from my MyMusik library."
PAIRING_SETTINGS_URI = "mymusik://pairing"


def saved_connection(profile_path):
    try:
        profile = bridge.load_profile(profile_path)
    except FileNotFoundError:
        return "new"
    except (bridge.BridgeError, OSError, ValueError, TypeError, KeyError):
        return "invalid"
    try:
        transport = bridge.Transport(profile["endpoint"], profile["origin"], profile["cookie"], timeout=4)
        status, _, body = transport.request("GET", "/ui/auth/status")
        if status != 200:
            return "unavailable"
        valid = bridge.json_object(body).get("tokenValid")
        if valid is False:
            return "renew"
        if valid is not True:
            return "unavailable"
        bridge.initialize(transport)
    except bridge.SessionDenied:
        return "renew"
    except (bridge.BridgeError, OSError, ValueError, KeyError, TypeError):
        return "unavailable"
    return "connected"


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
    args = ["stdio", "--profile", str(Path(profile_path).absolute())]
    if getattr(sys, "frozen", False):
        executable = executable.with_name("mymusik-mcp.exe")
    else:
        if os.name == "nt" and executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        args.insert(0, str(Path(__file__).resolve().with_name("cli.py")))
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
    available = set(font.families(root))
    for family in ("Roboto", "Segoe UI", "Helvetica Neue"):
        if family in available:
            base.configure(family=family)
            break
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

    # A stretchable corner tile rounds the native ttk buttons. Tk still
    # owns their keyboard, pointer, focus, disabled and accessible button states.
    radius = max(4, round(em * 0.33))
    images = []

    def corner_tile(fill, outline, background):
        def rgb(color):
            return tuple(c // 257 for c in root.winfo_rgb(color))

        inside, edge, outside = map(rgb, (fill, outline, background))
        size = 2 * radius + 1
        pixels = bytearray()
        for y in range(size):
            for x in range(size):
                distance = math.hypot(x - radius, y - radius)
                cover = min(1, max(0, radius + 0.5 - distance))
                inner = min(1, max(0, radius - 1.5 - distance))
                pixels.extend(round(a * inner + b * (cover - inner) + c * (1 - cover))
                              for a, b, c in zip(inside, edge, outside))
        image = tk.PhotoImage(data=f"P6\n{size} {size}\n255\n".encode() + pixels, format="PPM")
        images.append(image)
        return image

    def button_style(name, parent_bg, fill, fg, hover, pressed, outline=None):
        element = name + ".surface"
        style.element_create(element, "image", corner_tile(fill, outline or fill, parent_bg),
                             ("disabled", corner_tile("#e5deea", "#e5deea", parent_bg)),
                             ("pressed", corner_tile(pressed, accent, parent_bg)),
                             ("focus", corner_tile(hover, "#48206e" if fg != "white" else "#cca6ff", parent_bg)),
                             ("active", corner_tile(hover, outline or hover, parent_bg)),
                             border=radius, padding=0, sticky="nsew")
        style.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": ""})]})
        ]})])
        style.configure(name, foreground=fg, font=strong, padding=(2 * gap, gap + 1))
        style.map(name, foreground=[("disabled", muted)])

    button_style("Pair.TButton", surface, accent, "white", "#5c25a4", "#4d1b90")
    button_style("Next.TButton", paper, accent, "white", "#5c25a4", "#4d1b90")
    button_style("Open.TButton", surface, surface, ink, "#f5f0f9", "#eae1f0", "#b9adbf")
    button_style("Plain.TButton", paper, paper, accent, "#eee6f6", "#e4d7ee", "#998aa7")
    button_style("Link.TButton", surface, surface, accent, "#f4eff9", "#e3d8ed")

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

    hero = label(banner, "Connect your music player", header, "white", title)
    hero.pack(anchor="w", pady=(gap, 0))
    subtitle = label(banner, "Pair MyMusik with the MCP client on this computer.", header, "#dbd1e5",
                     wraplength=line_width + inset)
    subtitle.pack(anchor="w", pady=(gap // 2, 0))

    body = tk.Frame(root, bg=paper, padx=inset, pady=inset)
    body.pack(fill="x")

    def panel():
        return tk.Frame(body, bg=surface, padx=inset, pady=inset,
                        highlightthickness=1, highlightbackground="#ded7e4")

    pairing, recovery, connected = panel(), panel(), panel()

    def display(panel, heading_text, description):
        for frame in (pairing, recovery, connected):
            frame.pack_forget()
        panel.pack(fill="x", before=manual)
        hero.configure(text=heading_text)
        subtitle.configure(text=description)

    def action(parent, title, callback, style="Open.TButton"):
        return ttk.Button(parent, text=title, command=callback, style=style, cursor="hand2")

    def feedback(message):
        status.configure(text=message)
        status.pack(anchor="w", pady=(gap, 0))

    def open_player(uri, error_label):
        try:
            if os.name == "nt":
                os.startfile(uri)
            elif not webbrowser.open(uri):
                raise OSError()
        except OSError:
            error_label("Open MyMusik from your apps, or download it first.")

    label(pairing, "Choose your access", face=heading).pack(anchor="w")
    label(pairing, "Choose a permission preset and session duration in MyMusik, then select Apply.",
          fg=muted, wraplength=line_width).pack(anchor="w", pady=(gap // 2, gap))
    launch = tk.Frame(pairing, bg=surface)
    launch.pack(anchor="w")
    open_button = action(launch, "Open pairing settings", lambda: open_player(PAIRING_SETTINGS_URI, feedback))
    open_button.pack(side="left")
    action(launch, "Download MyMusik", lambda: webbrowser.open("https://mymusik.app/en/download/"),
           "Link.TButton").pack(side="left", padx=gap)
    manual_path = label(pairing, "Open the profile menu → Insights. On Connect a device, select the shield "
                        "at the right end of the header, above the QR code.", fg=muted, wraplength=line_width)

    def toggle_path():
        if manual_path.winfo_manager():
            manual_path.pack_forget()
            path_button.configure(text="Can’t find it?")
        else:
            manual_path.pack(anchor="w", before=divider, pady=(0, gap))
            path_button.configure(text="Hide directions")

    path_button = action(pairing, "Can’t find it?", toggle_path, "Link.TButton")
    path_button.pack(anchor="w")
    divider = tk.Frame(pairing, bg="#e6dfea", height=1)
    divider.pack(fill="x", pady=gap)
    label(pairing, "Pair this computer", face=heading).pack(anchor="w")
    label(pairing, "Below the QR code, select Copy agent prompt (AI agent in compact view). Then return here.",
          fg=muted, wraplength=line_width).pack(anchor="w", pady=(gap // 2, gap))
    results = queue.Queue()

    def pair_in_background(invitation):
        try:
            connect(invitation, profile_path)
        except bridge.BridgeError as error:
            results.put(("pair_error", str(error)))
        except (ValueError, OSError, KeyError, TypeError):
            results.put(("pair_error", "Pairing could not finish. Copy a fresh invitation and try again."))
        else:
            results.put(("connected", ""))

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
        pair_button.configure(text="Pairing…")
        status.pack_forget()
        threading.Thread(target=pair_in_background, args=(invitation,), daemon=True).start()
        root.after(80, finish)

    pair_button = action(pairing, "Paste invitation and pair", paste_and_pair, "Pair.TButton")
    pair_button.pack(anchor="w")
    status = label(pairing, "", fg="#922f3d", wraplength=line_width)

    def show_pairing():
        status.pack_forget()
        display(pairing, "Connect your music player", "Pair MyMusik with the MCP client on this computer.")
        open_button.focus_set()

    def probe():
        results.put((saved_connection(profile_path), ""))

    def check():
        display(recovery, "Checking your connection", "Contacting the player using your saved session…")
        recovery_hint.configure(text="Keep MyMusik open while setup checks.")
        recovery_actions.pack_forget()
        threading.Thread(target=probe, daemon=True).start()
        root.after(80, finish)

    recovery_hint = label(recovery, "", wraplength=line_width)
    recovery_hint.pack(anchor="w")
    recovery_actions = tk.Frame(recovery, bg=surface)
    retry = action(recovery_actions, "Retry", check, "Pair.TButton")
    retry.pack(side="left")
    action(recovery_actions, "Open MyMusik", lambda: open_player("mymusik://open",
           lambda msg: recovery_hint.configure(text=msg))).pack(side="left", padx=gap)
    action(recovery_actions, "Pair again", show_pairing, "Link.TButton").pack(side="left")

    label(connected, "Try it in your MCP client", face=heading).pack(anchor="w")
    prompt_hint = label(connected, FIRST_PROMPT, wraplength=line_width)
    prompt_hint.pack(anchor="w", pady=gap)
    connected_actions = tk.Frame(connected, bg=surface)
    connected_actions.pack(anchor="w")

    def copy(text, hint, success):
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
        except tk.TclError:
            hint.configure(text="Clipboard unavailable. " + (FIRST_PROMPT if hint == prompt_hint
                           else "Run mymusik-mcp config to get the settings."))
        else:
            hint.configure(text=success)

    first = action(connected_actions, "Copy first prompt", lambda: copy(FIRST_PROMPT, prompt_hint,
                   "Copied. Paste it into your MCP chat."), "Pair.TButton")
    first.pack(side="left")
    action(connected_actions, "Pair again", show_pairing, "Link.TButton").pack(side="left", padx=gap)

    def finish():
        try:
            state, message = results.get_nowait()
        except queue.Empty:
            root.after(80, finish)
            return
        pair_button.state(["!disabled"])
        pair_button.configure(text="Paste invitation and pair")
        if state == "connected":
            display(connected, "Your player is connected", "Open your MCP client or reconnect its MyMusik extension.")
            prompt_hint.configure(text=FIRST_PROMPT)
            first.focus_set()
        elif state == "unavailable":
            display(recovery, "Can’t reach your player", "Your saved session is still on this computer.")
            recovery_hint.configure(text="Open MyMusik on the paired device, check the network, then retry.")
            recovery_actions.pack(anchor="w", pady=(gap, 0))
            retry.focus_set()
        elif state == "pair_error":
            feedback(message)
        else:
            show_pairing()
            if state == "renew":
                subtitle.configure(text="Your saved access expired or was denied. Copy a new invitation to reconnect.")
            elif state == "invalid":
                subtitle.configure(text="Setup couldn’t read your saved session. Pair again to replace it.")

    manual = tk.Frame(body, bg=paper)
    manual.pack(fill="x", pady=(gap, 0))
    settings = tk.Frame(manual, bg=paper)

    def toggle_config():
        if settings.winfo_manager():
            settings.pack_forget()
        else:
            settings.pack(fill="x", pady=(gap, 0))

    action(manual, "Manual client setup", toggle_config, "Plain.TButton").pack(anchor="w")
    config_hint = label(settings, "For JSON clients, add the MyMusik entry to mcpServers.",
                        paper, muted, wraplength=line_width)
    config_hint.pack(anchor="w", pady=(0, gap))
    action(settings, "Copy client configuration", lambda: copy(json.dumps(client_config(profile_path), indent=2),
           config_hint, "Configuration copied. Add the entry alongside your existing servers."),
           "Plain.TButton").pack(anchor="w")

    show_pairing()
    root.update_idletasks()
    root.minsize(root.winfo_reqwidth(), 1)
    root.resizable(True, False)
    if Path(profile_path).exists():
        check()
    root.mainloop()
