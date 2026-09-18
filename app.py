"""
Diff Tool — a desktop app that compares two files or two folders and produces
a richly styled, self-contained HTML diff report.

Run:
    python app.py                     # launches the GUI
    python app.py --left A --right B --output out.html --mode auto   # headless

The GUI is built with CustomTkinter (a themed layer over Tk) for a modern
look while staying pure-Python / cross-platform. All the heavy lifting
(diffing, HTML report generation) lives in diff_engine.py / report_builder.py
so it can be exercised without a display, e.g. from CI.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from diff_engine import CompareOptions, compare_files, compare_folders
from report_builder import write_report

APP_TITLE = "Diff Tool"
APP_VERSION = "1.0"

ACCENT = "#E3B23C"
ACCENT_HOVER = "#C99A2E"
BG_DARK = "#0F1420"
PANEL_DARK = "#171D2E"
PANEL_DARK_2 = "#1E2740"
BORDER_DARK = "#2A3350"
TEXT_DARK = "#E7EAF2"
MUTED_DARK = "#8B93A7"
ADD_COLOR = "#4FAE74"
DEL_COLOR = "#D2604A"

DEFAULT_IGNORE_TEXT = ".git, __pycache__, node_modules, .venv, venv, .idea, .vscode, dist, build"


# ── Headless / CLI path (no GUI imports needed) ─────────────────────────────

def run_headless(left: str, right: str, output: str, mode: str,
                  ignore_whitespace: bool, ignore_dirs: str, open_after: bool) -> int:
    left_p, right_p = Path(left), Path(right)
    if not left_p.exists() or not right_p.exists():
        print(f"error: both paths must exist\n  left:  {left_p}\n  right: {right_p}", file=sys.stderr)
        return 2

    if mode == "auto":
        mode = "folders" if left_p.is_dir() else "files"

    options = CompareOptions(
        ignore_whitespace=ignore_whitespace,
        ignore_dirs={d.strip() for d in ignore_dirs.split(",") if d.strip()},
    )

    def _progress(msg: str) -> None:
        print(f"[diff-tool] {msg}")

    if mode == "folders":
        summary = compare_folders(left_p, right_p, options, progress=_progress)
    else:
        summary = compare_files(left_p, right_p, options, progress=_progress)

    out_path = write_report(summary, Path(output))
    c = summary.counts
    print(
        f"Report written to {out_path}\n"
        f"  modified={c['modified']} added={c['added']} removed={c['removed']} "
        f"unchanged={c['unchanged']} binary={c['binary']} too_large={c['too_large']} error={c['error']}\n"
        f"  +{summary.total_additions} / -{summary.total_deletions} lines · "
        f"{summary.elapsed_seconds:.2f}s"
    )
    if open_after:
        webbrowser.open(out_path.resolve().as_uri())
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="diff-tool", description="Diff Tool — visual diff report generator")
    p.add_argument("--left", help="Path to the original file/folder")
    p.add_argument("--right", help="Path to the modified file/folder")
    p.add_argument("--output", default=None, help="Output HTML report path")
    p.add_argument("--mode", choices=["auto", "files", "folders"], default="auto")
    p.add_argument("--ignore-whitespace", action="store_true")
    p.add_argument("--ignore-dirs", default=DEFAULT_IGNORE_TEXT)
    p.add_argument("--no-open", action="store_true", help="Do not open the report in a browser")
    p.add_argument("--gui", action="store_true", help="Force-launch the GUI")
    return p


# ── GUI ──────────────────────────────────────────────────────────────────────

def launch_gui() -> None:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    class DiffToolApp(ctk.CTk):
        def __init__(self) -> None:
            super().__init__()
            self.title(APP_TITLE)
            self.geometry("900x880")
            self.minsize(760, 700)
            self.configure(fg_color=BG_DARK)

            self.mode_var = ctk.StringVar(value="folders")
            self.left_var = ctk.StringVar()
            self.right_var = ctk.StringVar()
            self.output_var = ctk.StringVar(value=str(Path.cwd() / "diff_report.html"))
            self.ignore_ws_var = ctk.BooleanVar(value=False)
            self.open_after_var = ctk.BooleanVar(value=True)
            self.ignore_dirs_var = ctk.StringVar(value=DEFAULT_IGNORE_TEXT)

            self._build_header()
            self._build_mode_switch()
            self._build_path_pickers()
            self._build_options()
            self._build_action_row()
            self._build_log_panel()

            self._worker: threading.Thread | None = None

        # ── UI sections ──────────────────────────────────────────────────
        def _section_frame(self, expand: bool = False, **kw) -> "ctk.CTkFrame":
            kw.setdefault("fg_color", PANEL_DARK)
            kw.setdefault("corner_radius", 14)
            kw.setdefault("border_width", 1)
            kw.setdefault("border_color", BORDER_DARK)
            f = ctk.CTkFrame(self, **kw)
            f.pack(fill="both" if expand else "x", expand=expand, padx=26, pady=(0, 14))
            return f

        def _build_header(self) -> None:
            wrap = ctk.CTkFrame(self, fg_color="transparent")
            wrap.pack(fill="x", padx=26, pady=(22, 16))

            mark = ctk.CTkLabel(
                wrap, text="Δ", width=44, height=44, corner_radius=11,
                fg_color=ACCENT, text_color="#16130A",
                font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
            )
            mark.pack(side="left", padx=(0, 12))

            title_box = ctk.CTkFrame(wrap, fg_color="transparent")
            title_box.pack(side="left", fill="y")
            ctk.CTkLabel(
                title_box, text=APP_TITLE, text_color=TEXT_DARK,
                font=ctk.CTkFont(size=20, weight="bold"), anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                title_box, text="Stunning visual diff reports for files & folders",
                text_color=MUTED_DARK, font=ctk.CTkFont(size=12), anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                wrap, text=f"v{APP_VERSION}", text_color=MUTED_DARK, font=ctk.CTkFont(size=11),
            ).pack(side="right", anchor="n")

        def _build_mode_switch(self) -> None:
            frame = self._section_frame()
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="x", padx=18, pady=16)

            ctk.CTkLabel(inner, text="COMPARE", text_color=MUTED_DARK,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", pady=(0, 8))

            seg = ctk.CTkSegmentedButton(
                inner, values=["Two Folders", "Two Files"],
                fg_color=PANEL_DARK_2, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                unselected_color=PANEL_DARK_2, text_color=TEXT_DARK, text_color_disabled=MUTED_DARK,
                command=self._on_mode_change,
            )
            seg.set("Two Folders")
            seg.pack(fill="x")
            self._seg = seg

        def _on_mode_change(self, value: str) -> None:
            self.mode_var.set("folders" if value == "Two Folders" else "files")
            is_folder = self.mode_var.get() == "folders"
            self.left_label.configure(text="Original folder" if is_folder else "Original file")
            self.right_label.configure(text="Modified folder" if is_folder else "Modified file")
            # Clear paths that no longer make sense (folder chosen while in file mode etc.)
            for var in (self.left_var, self.right_var):
                p = var.get()
                if p and Path(p).exists():
                    if is_folder and not Path(p).is_dir():
                        var.set("")
                    elif not is_folder and not Path(p).is_file():
                        var.set("")

        def _path_row(self, parent, label_text: str, variable, browse_cmd) -> "ctk.CTkLabel":
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=6)
            lbl = ctk.CTkLabel(row, text=label_text, text_color=MUTED_DARK, width=120, anchor="w",
                                font=ctk.CTkFont(size=12))
            lbl.pack(side="left")
            entry = ctk.CTkEntry(row, textvariable=variable, fg_color=PANEL_DARK_2,
                                  border_color=BORDER_DARK, text_color=TEXT_DARK, height=34)
            entry.pack(side="left", fill="x", expand=True, padx=8)
            btn = ctk.CTkButton(row, text="Browse…", width=88, height=34, fg_color=PANEL_DARK_2,
                                 hover_color="#232E4C", text_color=TEXT_DARK, border_width=1,
                                 border_color=BORDER_DARK, command=browse_cmd)
            btn.pack(side="left")
            return lbl

        def _build_path_pickers(self) -> None:
            frame = self._section_frame()
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="x", padx=18, pady=16)

            self.left_label = self._path_row(inner, "Original folder", self.left_var, self._browse_left)
            self.right_label = self._path_row(inner, "Modified folder", self.right_var, self._browse_right)
            self._path_row(inner, "Save report as", self.output_var, self._browse_output)

        def _browse_left(self) -> None:
            self._browse_generic(self.left_var)

        def _browse_right(self) -> None:
            self._browse_generic(self.right_var)

        def _browse_generic(self, var) -> None:
            if self.mode_var.get() == "folders":
                path = filedialog.askdirectory(title="Select folder")
            else:
                path = filedialog.askopenfilename(title="Select file")
            if path:
                var.set(path)

        def _browse_output(self) -> None:
            path = filedialog.asksaveasfilename(
                title="Save report as", defaultextension=".html",
                filetypes=[("HTML report", "*.html")],
                initialfile="diff_report.html",
            )
            if path:
                self.output_var.set(path)

        def _build_options(self) -> None:
            frame = self._section_frame()
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="x", padx=18, pady=16)

            ctk.CTkLabel(inner, text="OPTIONS", text_color=MUTED_DARK,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", pady=(0, 10))

            row1 = ctk.CTkFrame(inner, fg_color="transparent")
            row1.pack(fill="x", pady=(0, 10))
            ctk.CTkCheckBox(row1, text="Ignore whitespace-only changes", variable=self.ignore_ws_var,
                             fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT_DARK,
                             checkmark_color="#16130A", border_color=BORDER_DARK).pack(side="left")
            ctk.CTkCheckBox(row1, text="Open report when done", variable=self.open_after_var,
                             fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT_DARK,
                             checkmark_color="#16130A", border_color=BORDER_DARK).pack(side="left", padx=(24, 0))

            row2 = ctk.CTkFrame(inner, fg_color="transparent")
            row2.pack(fill="x")
            ctk.CTkLabel(row2, text="Ignore folders", text_color=MUTED_DARK, width=120, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkEntry(row2, textvariable=self.ignore_dirs_var, fg_color=PANEL_DARK_2,
                         border_color=BORDER_DARK, text_color=TEXT_DARK, height=34).pack(
                side="left", fill="x", expand=True, padx=8)

        def _build_action_row(self) -> None:
            wrap = ctk.CTkFrame(self, fg_color="transparent")
            wrap.pack(fill="x", padx=26, pady=(0, 14))

            self.status_label = ctk.CTkLabel(wrap, text="Ready.", text_color=MUTED_DARK,
                                              font=ctk.CTkFont(size=12), anchor="w")
            self.status_label.pack(side="left", fill="x", expand=True)

            self.generate_btn = ctk.CTkButton(
                wrap, text="Generate Diff Report", height=42, width=200,
                fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#16130A",
                font=ctk.CTkFont(size=13, weight="bold"), command=self._on_generate,
            )
            self.generate_btn.pack(side="right")

        def _build_log_panel(self) -> None:
            frame = self._section_frame(expand=True)
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=18, pady=16)

            ctk.CTkLabel(inner, text="ACTIVITY", text_color=MUTED_DARK,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", pady=(0, 8))

            self.progress = ctk.CTkProgressBar(inner, mode="indeterminate", fg_color=PANEL_DARK_2,
                                                progress_color=ACCENT)
            self.progress.pack(fill="x", pady=(0, 10))

            self.log_box = ctk.CTkTextbox(inner, fg_color="#0B0F19", text_color=MUTED_DARK,
                                           border_width=1, border_color=BORDER_DARK,
                                           font=ctk.CTkFont(family="Consolas", size=12))
            self.log_box.pack(fill="both", expand=True)
            self.log_box.configure(state="disabled")

        # ── Logging helpers ──────────────────────────────────────────────
        def _log(self, msg: str) -> None:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{stamp}] {msg}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        def _set_busy(self, busy: bool) -> None:
            self.generate_btn.configure(state="disabled" if busy else "normal",
                                         text="Working…" if busy else "Generate Diff Report")
            if busy:
                self.progress.start()
            else:
                self.progress.stop()

        # ── Validation & run ─────────────────────────────────────────────
        def _validate(self) -> tuple[Path, Path] | None:
            left, right = self.left_var.get().strip(), self.right_var.get().strip()
            if not left or not right:
                messagebox.showwarning(APP_TITLE, "Please choose both the original and modified paths.")
                return None
            left_p, right_p = Path(left), Path(right)
            if not left_p.exists():
                messagebox.showerror(APP_TITLE, f"Original path does not exist:\n{left_p}")
                return None
            if not right_p.exists():
                messagebox.showerror(APP_TITLE, f"Modified path does not exist:\n{right_p}")
                return None
            is_folder_mode = self.mode_var.get() == "folders"
            if is_folder_mode and (not left_p.is_dir() or not right_p.is_dir()):
                messagebox.showerror(APP_TITLE, "Folder mode is selected — both paths must be folders.")
                return None
            if not is_folder_mode and (not left_p.is_file() or not right_p.is_file()):
                messagebox.showerror(APP_TITLE, "File mode is selected — both paths must be files.")
                return None
            if left_p.resolve() == right_p.resolve():
                if not messagebox.askyesno(APP_TITLE, "Both paths are identical. Generate a report anyway?"):
                    return None
            return left_p, right_p

        def _on_generate(self) -> None:
            if self._worker and self._worker.is_alive():
                return
            paths = self._validate()
            if paths is None:
                return
            left_p, right_p = paths
            output = self.output_var.get().strip() or str(Path.cwd() / "diff_report.html")

            self._set_busy(True)
            self.status_label.configure(text="Comparing…")
            self._log(f"Starting comparison ({self.mode_var.get()})")
            self._log(f"  left:  {left_p}")
            self._log(f"  right: {right_p}")

            options = CompareOptions(
                ignore_whitespace=self.ignore_ws_var.get(),
                ignore_dirs={d.strip() for d in self.ignore_dirs_var.get().split(",") if d.strip()},
            )

            def progress_cb(msg: str) -> None:
                self.after(0, self._log, msg)

            def work() -> None:
                try:
                    if self.mode_var.get() == "folders":
                        summary = compare_folders(left_p, right_p, options, progress=progress_cb)
                    else:
                        summary = compare_files(left_p, right_p, options, progress=progress_cb)
                    out_path = write_report(summary, Path(output))
                except Exception as exc:  # noqa: BLE001
                    self.after(0, self._on_error, str(exc))
                    return
                self.after(0, self._on_done, summary, out_path)

            self._worker = threading.Thread(target=work, daemon=True)
            self._worker.start()

        def _on_error(self, message: str) -> None:
            self._set_busy(False)
            self.status_label.configure(text="Failed.")
            self._log(f"ERROR: {message}")
            messagebox.showerror(APP_TITLE, f"Could not generate the report:\n{message}")

        def _on_done(self, summary, out_path: Path) -> None:
            self._set_busy(False)
            c = summary.counts
            self.status_label.configure(
                text=f"Done — {c['modified']} modified, {c['added']} added, {c['removed']} removed "
                     f"({summary.elapsed_seconds:.2f}s)"
            )
            self._log(
                f"Report saved to {out_path}  "
                f"(+{summary.total_additions} / -{summary.total_deletions} lines)"
            )
            if self.open_after_var.get():
                webbrowser.open(out_path.resolve().as_uri())

    DiffToolApp().mainloop()


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    headless_requested = bool(args.left or args.right) and not args.gui
    if headless_requested:
        if not args.left or not args.right:
            parser.error("--left and --right are both required for headless mode")
        output = args.output or str(Path.cwd() / "diff_report.html")
        return run_headless(
            left=args.left, right=args.right, output=output, mode=args.mode,
            ignore_whitespace=args.ignore_whitespace, ignore_dirs=args.ignore_dirs,
            open_after=not args.no_open,
        )

    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
