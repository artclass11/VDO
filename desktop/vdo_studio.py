from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vdo.post.core import COLOR_STYLES, EDITOR_CAPABILITIES, create_post_package

OLLAMA_BASE = "http://127.0.0.1:11434"
SYSTEM_PROMPT = (
    "You are VDO Studio, a documentary editor and colorist assistant. "
    "Transform a user's rough idea into a concise, practical editing brief for a real human editor. "
    "Preserve their facts; do not invent sources, quotes, dates or claims. "
    "Specify story arc, hook, scene order, B-roll ideas, interview beats, pacing, sound design, "
    "caption/graphic restraint, color intent and delivery checks. Keep it actionable and grounded."
)


class VDOStudio:
    BG = "#08090b"
    PANEL = "#101216"
    TEXT = "#f2f4f7"
    MUTED = "#a3aab5"
    ACCENT = "#d8dee8"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("VDO Studio — Offline Post Production")
        self.root.geometry("930x780")
        self.root.minsize(760, 680)
        self.root.configure(bg=self.BG)
        self.media_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "VDO Projects"))
        self.model = tk.StringVar(value=os.getenv("VDO_OLLAMA_MODEL", "qwen3:8b"))
        self.editor = tk.StringVar(value="resolve")
        self.look = tk.StringVar(value="neutral_documentary")
        self.fps = tk.StringVar(value="24")
        self.duration = tk.StringVar(value="180")
        self.project_name = tk.StringVar(value="My Documentary")
        self.status = tk.StringVar(value="LOCAL ONLY · start Ollama and load a model before generating a package.")
        self._build()
        self.root.after(500, self.refresh_models)

    def _build(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=self.PANEL, background=self.PANEL, foreground=self.TEXT, arrowcolor=self.TEXT)
        style.configure("TButton", background=self.PANEL, foreground=self.TEXT, padding=(10, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#252a33")])
        outer = tk.Frame(self.root, bg=self.BG, padx=24, pady=20)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="VDO STUDIO", bg=self.BG, fg=self.TEXT, font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(outer, text="OFFLINE DOCUMENTARY / FILM POST-PRODUCTION", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 18))

        self._section(outer, "01  MEDIA")
        self._path_row(outer, "Source folder", self.media_dir, self._choose_media)
        self._path_row(outer, "Output folder", self.output_dir, self._choose_output)

        self._section(outer, "02  DIRECT THE EDIT")
        tk.Label(outer, text="Describe the film in plain language", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 5))
        self.brief = tk.Text(outer, height=5, wrap="word", bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", padx=12, pady=10, font=("Segoe UI", 11))
        self.brief.pack(fill="x")
        self.brief.insert("1.0", "A human-centred documentary with observational B-roll, natural pacing, restrained titles, clear dialogue and a subtle cinematic finish.")

        options = tk.Frame(outer, bg=self.BG)
        options.pack(fill="x", pady=(12, 8))
        self._field(options, "Target editor", self.editor, list(EDITOR_CAPABILITIES.keys()), 0)
        self._field(options, "Color look", self.look, list(COLOR_STYLES), 1)
        self._field(options, "Frame rate", self.fps, ["23.976", "24", "25", "29.97", "30", "50", "59.94", "60"], 2)
        self._field(options, "Target seconds", self.duration, [], 3)
        self._field(options, "Project title", self.project_name, [], 4)

        row = tk.Frame(outer, bg=self.BG)
        row.pack(fill="x", pady=(8, 8))
        ttk.Button(row, text="Refresh local models", command=self.refresh_models).pack(side="left")
        self.model_box = ttk.Combobox(row, textvariable=self.model, width=20)
        self.model_box.pack(side="left", padx=(8, 12))
        ttk.Button(row, text="Build offline edit package", command=self.build).pack(side="right")

        tk.Label(outer, textvariable=self.status, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=850, justify="left").pack(fill="x", pady=(8, 4))
        tk.Label(outer, text="Local model inference only: 127.0.0.1 · no cloud endpoints · media remains on this computer.", bg=self.BG, fg="#737b87", font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 0))

    def _section(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, bg=self.BG, fg=self.ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 4))

    def _path_row(self, parent: tk.Widget, label: str, variable: tk.StringVar, callback) -> None:
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text=label, width=15, anchor="w", bg=self.BG, fg=self.MUTED).pack(side="left")
        entry = tk.Entry(frame, textvariable=variable, bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        ttk.Button(frame, text="Choose", command=callback).pack(side="right")

    def _field(self, parent: tk.Widget, label: str, variable: tk.StringVar, values: list[str], column: int) -> None:
        frame = tk.Frame(parent, bg=self.BG)
        frame.grid(row=0, column=column, sticky="ew", padx=(0, 8))
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(frame, text=label, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        if values:
            box = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly", width=18)
            box.pack(fill="x")
            if variable is self.editor:
                box.bind("<<ComboboxSelected>>", lambda _: self._show_editor_name())
        else:
            entry = tk.Entry(frame, textvariable=variable, bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat")
            entry.pack(fill="x", ipady=7)

    def _show_editor_name(self) -> None:
        self.status.set(f"Target: {EDITOR_CAPABILITIES[self.editor.get()]['label']} · portable, reviewable handoff")

    def _choose_media(self) -> None:
        path = filedialog.askdirectory(title="Choose source media folder")
        if path:
            self.media_dir.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_dir.set(path)

    def _local_request(self, route: str, payload: dict, timeout: int = 300) -> dict:
        url = OLLAMA_BASE + route
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Could not reach the local Ollama model. Install/start Ollama, download the model once, "
                "then run this app offline. Expected local endpoint: " + OLLAMA_BASE + f" ({exc})"
            ) from exc

    def refresh_models(self) -> None:
        def task() -> None:
            try:
                with urlopen(OLLAMA_BASE + "/api/tags", timeout=3) as response:
                    data = json.loads(response.read().decode("utf-8"))
                names = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
                def done() -> None:
                    self.model_box.configure(values=names)
                    if names and self.model.get() not in names:
                        self.model.set(names[0])
                    self.status.set(f"LOCAL MODEL READY · {len(names)} model(s) available." if names else "OLLama reachable, but no local models are installed.")
                self.root.after(0, done)
            except Exception:
                self.root.after(0, lambda: self.status.set("LOCAL MODEL OFFLINE · start Ollama and pull a model once; no cloud fallback is used."))
        threading.Thread(target=task, daemon=True).start()

    def build(self) -> None:
        media = self.media_dir.get().strip()
        output = self.output_dir.get().strip()
        brief = self.brief.get("1.0", "end").strip()
        model = self.model.get().strip()
        if not media or not Path(media).is_dir():
            messagebox.showerror("Choose media", "Select a valid local media folder first.")
            return
        if not output or not brief:
            messagebox.showerror("Missing information", "Enter an output folder and documentary brief.")
            return
        try:
            target_duration = float(self.duration.get().strip())
            frame_rate = float(self.fps.get().strip())
            if target_duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid settings", "Target seconds must be positive and frame rate must be numeric.")
            return
        if not model:
            messagebox.showerror("Local model required", "Select an installed local Ollama model. VDO never uses a cloud fallback.")
            return

        # Read all Tk state on the UI thread before the worker starts. The
        # background thread must use an immutable job snapshot, never Tcl vars.
        project_name = self.project_name.get().strip() or "VDO Documentary"
        editor_key = self.editor.get()
        editor_label = EDITOR_CAPABILITIES[editor_key]["label"]
        color_style = self.look.get()

        for widget in self.root.winfo_children():
            self._set_children_state(widget, "disabled")
        self.status.set("WORKING LOCALLY · asking the local LLM to refine the edit brief…")

        def task() -> None:
            try:
                prompt = (
                    f"{SYSTEM_PROMPT}\n\nPROJECT TITLE: {project_name}\n"
                    f"TARGET EDITOR: {editor_label}\n"
                    f"TARGET LENGTH: {target_duration} seconds\nCOLOR INTENT: {color_style}\n"
                    f"USER BRIEF:\n{brief}\n\nReturn the refined production brief in plain text, with concise scenes and edit notes."
                )
                result = self._local_request("/api/generate", {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "10m",
                    "options": {"temperature": 0.25, "num_predict": 1400},
                })
                refined = str(result.get("response", "")).strip()
                if not refined:
                    raise RuntimeError("The local model returned an empty production brief.")
                package = create_post_package(
                    media_dir=media,
                    output_dir=output,
                    brief=refined,
                    editor=editor_key,
                    duration_seconds=target_duration,
                    project_name=project_name,
                    fps=frame_rate,
                    color_style=color_style,
                )
                (Path(output) / "LOCAL_LLM_EDIT_BRIEF.txt").write_text(refined + "\n", encoding="utf-8")
                self.root.after(0, lambda: self._completed(package))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self._failed(err))

        threading.Thread(target=task, daemon=True).start()

    def _set_children_state(self, widget: tk.Widget, state: str) -> None:
        try:
            if isinstance(widget, (tk.Button, tk.Entry, tk.Text, ttk.Button, ttk.Combobox)):
                widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_children_state(child, state)

    def _completed(self, package: dict) -> None:
        self._set_children_state(self.root, "normal")
        self.status.set(f"PACKAGE READY · {package['decision_count']} edit decisions · {package['actual_duration_seconds']}s · {package['output_dir']}")
        messagebox.showinfo("VDO package ready", "Created a local editorial/color handoff package.\n\nReview EDIT_PLAN.json before picture lock.")

    def _failed(self, error: str) -> None:
        self._set_children_state(self.root, "normal")
        self.status.set("BUILD FAILED · no cloud fallback was used.")
        messagebox.showerror("VDO build failed", error)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    VDOStudio().run()
