"""PIPROOM — кроссплатформенный тёмный менеджер Python-пакетов."""
from __future__ import annotations

import io
import queue
import re
import struct
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable
import shlex

from PIL import Image, ImageDraw, ImageTk

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit(
        "Не найдена CustomTkinter. Выполните в CMD:\n"
        "py -m pip install customtkinter\n"
        "Затем запустите программу снова."
    ) from exc


APP_TITLE = "PIPROOM · Package Manager"

# Единая графитовая палитра. Ни один крупный элемент не использует белую заливку.
C = {
    "bg": "#090D12",
    "sidebar": "#0D131A",
    "surface": "#111922",
    "surface_2": "#151F2A",
    "surface_3": "#1A2632",
    "input": "#0B1118",
    "line": "#253342",
    "line_soft": "#1C2834",
    "text": "#E8EEF4",
    "text_soft": "#A7B4C2",
    "muted": "#718092",
    "accent": "#168AAD",
    "accent_hover": "#219FC2",
    "accent_ink": "#F4FAFC",
    "cyan": "#62B9D2",
    "success": "#85D7A4",
    "success_bg": "#14271F",
    "warning": "#E8BC76",
    "warning_bg": "#2A2115",
    "danger": "#F08A8A",
    "danger_bg": "#2B191D",
}

PACKAGE_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"(?:\[[A-Za-z0-9_,.-]+\])?"
    r"\s*(?:(?:===|==|~=|!=|<=|>=|<|>)\s*[A-Za-z0-9][A-Za-z0-9.*+!_-]*)?$"
)

FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica Neue"
MONO = "Cascadia Mono" if sys.platform == "win32" else "Menlo"


class PyLibraryManager(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x790")
        self.minsize(940, 680)
        self.configure(fg_color=C["bg"])

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.is_busy = False
        self.upgrade_var = ctk.BooleanVar(value=False)
        self.quick_buttons: list[ctk.CTkButton] = []
        self.brand_logo_image = self._make_logo_image(48)
        # Keep a reference to the Tk image: without it Tk may discard the window icon.
        self._window_icon_photo = ImageTk.PhotoImage(self._make_logo_pil(128))
        self.iconphoto(True, self._window_icon_photo)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_workspace()

        self.bind("<Return>", self._on_enter)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)

    @staticmethod
    def _make_logo_pil(size: int) -> Image.Image:
        """Draw the PIPROOM ocean mark at high resolution for UI and window icons."""
        scale = 4
        canvas_size = size * scale
        image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        def pt(x: float, y: float) -> tuple[int, int]:
            return (round(x * canvas_size / 64), round(y * canvas_size / 64))

        draw.rounded_rectangle(
            (pt(2, 2), pt(62, 62)), radius=round(17 * canvas_size / 64),
            fill="#102431", outline="#244655", width=max(1, scale),
        )

        def bezier(p0, p1, p2, p3, steps=64):
            points = []
            for i in range(steps + 1):
                t = i / steps
                u = 1 - t
                x = u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0]
                y = u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]
                points.append(pt(x, y))
            return points

        stroke = max(4, round(5 * canvas_size / 64))
        draw.line(
            bezier((12, 24), (18, 15), (27, 15), (34, 22))
            + bezier((34, 22), (41, 29), (46, 29), (53, 21))[1:],
            fill="#38B4D2", width=stroke, joint="curve",
        )
        draw.line(
            bezier((11, 37), (19, 28), (28, 28), (35, 35))
            + bezier((35, 35), (42, 42), (47, 42), (54, 34))[1:],
            fill="#168AAD", width=stroke, joint="curve",
        )
        draw.line(
            bezier((14, 49), (22, 42), (29, 43), (36, 48)),
            fill="#7CD2E2", width=max(3, round(4 * canvas_size / 64)),
            joint="curve",
        )
        return image.resize((size, size), Image.Resampling.LANCZOS)

    @classmethod
    def _make_logo_image(cls, size: int) -> ctk.CTkImage:
        image = cls._make_logo_pil(size)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    # ----- Layout -----
    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(
            self, width=232, corner_radius=0, fg_color=C["sidebar"],
            border_width=1, border_color=C["line_soft"],
        )
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(5, weight=1)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=22, pady=(27, 38))
        brand.grid_columnconfigure(1, weight=1)

        # The SVG is the source of truth for the mark. Pillow draws the same
        # compact vector strokes at runtime so no extra SVG package is needed.
        mark = ctk.CTkLabel(
            brand, text="", image=self.brand_logo_image,
            width=48, height=48, fg_color="transparent",
        )
        mark.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))

        ctk.CTkLabel(
            brand, text="PIPROOM", text_color=C["text"],
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
        ).grid(row=0, column=1, sticky="sw", pady=(2, 0))
        ctk.CTkLabel(
            brand, text="PYTHON PACKAGE TOOL", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=8, weight="bold"),
        ).grid(row=1, column=1, sticky="nw", pady=(1, 0))

        ctk.CTkLabel(
            side, text="РАБОЧЕЕ ПРОСТРАНСТВО", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=9, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=23, pady=(0, 10))

        nav = ctk.CTkFrame(
            side, fg_color=C["surface_2"], corner_radius=10,
            border_width=1, border_color=C["line"],
        )
        nav.grid(row=2, column=0, sticky="ew", padx=14)
        nav.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(nav, width=3, height=34, fg_color=C["accent"], corner_radius=2).grid(
            row=0, column=0, sticky="nsw", padx=(0, 11), pady=8
        )
        ctk.CTkLabel(
            nav, text="01", text_color=C["accent"],
            font=ctk.CTkFont(family=MONO, size=10, weight="bold"),
        ).grid(row=0, column=1, sticky="w", pady=11)
        ctk.CTkLabel(
            nav, text="Установка пакетов", text_color=C["text"],
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
        ).grid(row=0, column=2, sticky="w", padx=(10, 14), pady=11)

        ctk.CTkLabel(
            side, text="АКТИВНАЯ СРЕДА", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=9, weight="bold"),
        ).grid(row=3, column=0, sticky="sw", padx=23, pady=(34, 10))

        env = ctk.CTkFrame(
            side, fg_color=C["surface"], corner_radius=12,
            border_width=1, border_color=C["line_soft"],
        )
        env.grid(row=4, column=0, sticky="ew", padx=14)
        env.grid_columnconfigure(0, weight=1)

        version = sys.version.split()[0]
        ctk.CTkLabel(
            env, text="PYTHON", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=9, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(13, 2))
        ctk.CTkLabel(
            env, text=f"{version}", text_color=C["text"],
            font=ctk.CTkFont(family=MONO, size=16, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=14)
        ctk.CTkLabel(
            env, text="Путь интерпретатора", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=9),
        ).grid(row=2, column=0, sticky="w", padx=14, pady=(12, 3))
        ctk.CTkLabel(
            env, text=sys.executable, text_color=C["text_soft"],
            font=ctk.CTkFont(family=MONO, size=9), wraplength=174,
            justify="left",
        ).grid(row=3, column=0, sticky="w", padx=14)

        self.copy_command_button = ctk.CTkButton(
            env, text="КОПИРОВАТЬ pip list", height=29, corner_radius=7,
            fg_color=C["surface_3"], hover_color="#1B3442",
            text_color=C["text_soft"], border_width=1, border_color=C["line"],
            font=ctk.CTkFont(family=FONT, size=9, weight="bold"),
            command=self._copy_pip_command,
        )
        self.copy_command_button.grid(row=4, column=0, sticky="ew", padx=11, pady=(13, 11))

        ctk.CTkFrame(side, height=1, fg_color=C["line_soft"]).grid(
            row=6, column=0, sticky="ew", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(
            side, text=f"LOCAL INSTALLER  /  {'WINDOWS' if sys.platform == 'win32' else 'MACOS' if sys.platform == 'darwin' else sys.platform.upper()}", text_color=C["muted"],
            font=ctk.CTkFont(family=MONO, size=8),
        ).grid(row=7, column=0, sticky="w", padx=22, pady=(0, 20))

    def _build_workspace(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(30, 32), pady=(27, 24))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        self._build_header(main)
        self._build_installer(main)
        self._build_log(main)

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 22))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="PYTHON  /  ENVIRONMENT", text_color=C["cyan"],
            font=ctk.CTkFont(family=MONO, size=10, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ctk.CTkLabel(
            header, text="Пакеты Python", text_color=C["text"],
            font=ctk.CTkFont(family=FONT, size=30, weight="bold"),
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Установка в интерпретатор, которым запущено это окно.",
            text_color=C["text_soft"],
            font=ctk.CTkFont(family=FONT, size=12),
        ).grid(row=2, column=0, sticky="w", pady=(3, 0))

        self.status_pill = ctk.CTkLabel(
            header, text="●  ОЖИДАНИЕ", text_color=C["success"],
            fg_color=C["success_bg"], corner_radius=7, height=31,
            font=ctk.CTkFont(family=MONO, size=9, weight="bold"),
            padx=12,
        )
        self.status_pill.grid(row=0, column=1, rowspan=2, sticky="ne", pady=(2, 0))

    def _build_installer(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(
            parent, fg_color=C["surface"], corner_radius=15,
            border_width=1, border_color=C["line"],
        )
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        panel.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=22, pady=(19, 14))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            top, text="Добавить пакет", text_color=C["text"],
            font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            top, text="pip install", text_color=C["accent"],
            font=ctk.CTkFont(family=MONO, size=10, weight="bold"),
        ).grid(row=0, column=1, sticky="e")

        entry_row = ctk.CTkFrame(panel, fg_color="transparent")
        entry_row.grid(row=1, column=0, sticky="ew", padx=22)
        entry_row.grid_columnconfigure(0, weight=1)

        self.package_entry = ctk.CTkEntry(
            entry_row, height=47, corner_radius=9,
            border_width=1, border_color=C["line"],
            fg_color=C["input"], text_color=C["text"],
            placeholder_text="Название пакета или несколько через запятую",
            placeholder_text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=13),
        )
        self.package_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.install_button = ctk.CTkButton(
            entry_row, text="Установить  ↗", width=148, height=47,
            corner_radius=9, fg_color=C["accent"], hover_color=C["accent_hover"],
            text_color=C["accent_ink"],
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._start_install,
        )
        self.install_button.grid(row=0, column=1)

        examples = ctk.CTkFrame(panel, fg_color="transparent")
        examples.grid(row=2, column=0, sticky="ew", padx=22, pady=(12, 16))
        ctk.CTkLabel(
            examples, text="БЫСТРЫЙ ВВОД", text_color=C["muted"],
            font=ctk.CTkFont(family=MONO, size=8, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        for package in ("pandas", "requests", "numpy", "pygame-ce", "customtkinter"):
            btn = ctk.CTkButton(
                examples, text=package, height=25, width=0,
                corner_radius=6, fg_color=C["surface_3"], hover_color="#1D3D4D",
                text_color=C["text_soft"], border_width=1, border_color=C["line"],
                font=ctk.CTkFont(family=MONO, size=9),
                command=lambda name=package: self._quick_fill(name),
            )
            btn.pack(side="left", padx=(0, 6))
            self.quick_buttons.append(btn)

        divider = ctk.CTkFrame(panel, height=1, fg_color=C["line_soft"])
        divider.grid(row=3, column=0, sticky="ew", padx=22)

        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.grid(row=4, column=0, sticky="ew", padx=22, pady=(13, 10))
        controls.grid_columnconfigure(0, weight=1)

        self.upgrade_checkbox = ctk.CTkCheckBox(
            controls, text="Обновить, если пакет уже установлен",
            variable=self.upgrade_var, checkbox_width=17, checkbox_height=17,
            corner_radius=4, border_color=C["muted"], fg_color=C["accent"],
            hover_color=C["accent_hover"], text_color=C["text_soft"],
            checkmark_color=C["accent_ink"],
            font=ctk.CTkFont(family=FONT, size=10),
        )
        self.upgrade_checkbox.grid(row=0, column=0, sticky="w")

        self.update_pip_button = ctk.CTkButton(
            controls, text="Обновить pip", height=29, width=112,
            corner_radius=7, fg_color="transparent", hover_color=C["surface_3"],
            text_color=C["text_soft"], border_width=1, border_color=C["line"],
            font=ctk.CTkFont(family=FONT, size=10), command=self._start_pip_update,
        )
        self.update_pip_button.grid(row=0, column=1, sticky="e")

        progress_row = ctk.CTkFrame(panel, fg_color="transparent")
        progress_row.grid(row=5, column=0, sticky="ew", padx=22, pady=(5, 19))
        progress_row.grid_columnconfigure(0, weight=1)
        self.progress_text = ctk.CTkLabel(
            progress_row, text="Можно начинать установку", text_color=C["muted"],
            font=ctk.CTkFont(family=FONT, size=10),
        )
        self.progress_text.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.progress_state = ctk.CTkLabel(
            progress_row, text="ГОТОВ", text_color=C["muted"],
            font=ctk.CTkFont(family=MONO, size=8, weight="bold"),
        )
        self.progress_state.grid(row=0, column=1, sticky="e", pady=(0, 8))
        self.progress = ctk.CTkProgressBar(
            progress_row, height=5, corner_radius=3,
            fg_color=C["surface_3"], progress_color=C["accent"],
            mode="determinate",
        )
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.progress.set(0)

    def _build_log(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(
            parent, fg_color=C["surface"], corner_radius=15,
            border_width=1, border_color=C["line"],
        )
        panel.grid(row=2, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(15, 11))
        toolbar.grid_columnconfigure(1, weight=1)

        lights = ctk.CTkFrame(toolbar, fg_color="transparent")
        lights.grid(row=0, column=0, sticky="w", padx=(0, 12))
        for color in ("#E27D76", "#E6BD70", "#85C98D"):
            ctk.CTkFrame(lights, width=7, height=7, corner_radius=4, fg_color=color).pack(
                side="left", padx=(0, 4)
            )

        ctk.CTkLabel(
            toolbar, text="ВЫВОД УСТАНОВЩИКА", text_color=C["text_soft"],
            font=ctk.CTkFont(family=MONO, size=9, weight="bold"),
        ).grid(row=0, column=1, sticky="w")

        self.clear_button = ctk.CTkButton(
            toolbar, text="Очистить", width=68, height=26,
            corner_radius=6, fg_color="transparent", hover_color=C["surface_3"],
            text_color=C["muted"], font=ctk.CTkFont(family=FONT, size=9),
            command=self._clear_log,
        )
        self.clear_button.grid(row=0, column=2, sticky="e")

        self.log_box = ctk.CTkTextbox(
            panel, corner_radius=8, border_width=1,
            border_color=C["line_soft"], fg_color=C["input"],
            text_color="#C5D1DD", font=ctk.CTkFont(family=MONO, size=10),
            wrap="word", scrollbar_button_color=C["surface_3"],
            scrollbar_button_hover_color="#28566B",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_box.configure(state="disabled")

        self._append_log("PIPROOM готов. Введи имя пакета или выбери пример выше.")
        self._append_log(f"Python {sys.version.split()[0]} · {sys.executable}")
        self._append_log("Все операции выполняются через этот интерпретатор: sys.executable -m pip")

    # ----- UI helpers -----
    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{timestamp}   {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _copy_pip_command(self) -> None:
        command = shlex.join([sys.executable, "-m", "pip", "list"])
        self.clipboard_clear()
        self.clipboard_append(command)
        self.copy_command_button.configure(text="СКОПИРОВАНО")
        self._append_log(f"Команда скопирована: {command}")
        self.after(1600, lambda: self.copy_command_button.configure(text="КОПИРОВАТЬ pip list"))

    def _quick_fill(self, package: str) -> None:
        if self.is_busy:
            return
        self.package_entry.delete(0, "end")
        self.package_entry.insert(0, package)
        self.package_entry.focus_set()

    def _clear_log(self) -> None:
        if self.is_busy:
            return
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._append_log("Журнал очищен.")

    def _on_enter(self, _event=None) -> None:
        if not self.is_busy:
            self._start_install()

    @staticmethod
    def _parse_packages(raw: str) -> list[str]:
        packages = [part.strip() for part in re.split(r"[,;\n]+", raw.strip()) if part.strip()]
        if not packages:
            raise ValueError("Введи название библиотеки.")
        invalid = [item for item in packages if not PACKAGE_PATTERN.fullmatch(item)]
        if invalid:
            raise ValueError(
                "Не удалось распознать: " + ", ".join(invalid)
                + ". Укажи только имя пакета и, при необходимости, его версию, например pandas==2.2.3."
            )
        return packages

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.install_button, self.update_pip_button, self.package_entry,
            self.upgrade_checkbox, self.clear_button,
        ):
            widget.configure(state=state)
        for button in self.quick_buttons:
            button.configure(state=state)

    def _start_install(self) -> None:
        if self.is_busy:
            return
        try:
            packages = self._parse_packages(self.package_entry.get())
        except ValueError as exc:
            self._append_log(f"Проверка ввода: {exc}")
            self._set_status("ПРОВЕРЬ ВВОД", "warning")
            return

        self._begin_task(f"Установка {len(packages)} пак. …")
        self._append_log("Установка: " + ", ".join(packages))
        self._append_log(f"Целевой Python: {sys.executable}")
        self.worker = threading.Thread(
            target=self._install_worker,
            args=(packages, self.upgrade_var.get()),
            daemon=True,
        )
        self.worker.start()

    def _start_pip_update(self) -> None:
        if self.is_busy:
            return
        self._begin_task("Обновление pip…")
        self._append_log("Обновление pip запущено.")
        self.worker = threading.Thread(
            target=self._install_worker, args=(["pip"], True), daemon=True
        )
        self.worker.start()

    def _begin_task(self, label: str) -> None:
        self._set_busy(True)
        self._set_status("УСТАНОВКА", "active")
        self.progress_text.configure(text=label)
        self.progress_state.configure(text="В ПРОЦЕССЕ", text_color=C["accent"])
        self.progress.configure(mode="indeterminate")
        self.progress.start()

    def _set_status(self, label: str, kind: str) -> None:
        palette = {
            "success": (C["success"], C["success_bg"]),
            "active": (C["cyan"], "#102A35"),
            "warning": (C["warning"], C["warning_bg"]),
            "danger": (C["danger"], C["danger_bg"]),
        }
        fg, bg = palette.get(kind, (C["text_soft"], C["surface_2"]))
        self.status_pill.configure(text=f"●  {label}", text_color=fg, fg_color=bg)

    # ----- pip worker -----
    def _install_worker(self, packages: Iterable[str], upgrade: bool) -> None:
        package_list = list(packages)
        results: list[tuple[str, bool]] = []
        for index, package in enumerate(package_list, start=1):
            install_target = package
            # Classic pygame 2.6.1 does not provide a CPython 3.14 Windows wheel.
            # On Python 3.14+, route a plain `pygame` request to pygame-ce, a
            # compatible community edition that keeps the `import pygame` API.
            # Explicitly pinned requests (pygame==...) are left untouched.
            if sys.version_info >= (3, 14) and package.strip().lower() == "pygame":
                install_target = "pygame-ce"
                self.events.put((
                    "log",
                    "Совместимость Python 3.14: вместо классического pygame будет "
                    "установлен pygame-ce (совместимая замена; импорт остаётся: import pygame)."
                ))

            self.events.put(("package_start", (index, len(package_list), package)))
            if install_target != package:
                self.events.put(("log", f"Целевой пакет для pip: {install_target}"))
            command = [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--no-input", "--progress-bar", "off",
            ]
            if upgrade:
                command.append("--upgrade")
            command.append(install_target)
            success = self._run_command(command)
            if success and install_target != package:
                self.events.put(("log", "Установлен pygame-ce. В Python-коде используй: import pygame"))
            results.append((package, success))
            self.events.put(("package_done", (index, len(package_list), package, success)))
        self.events.put(("finished", results))

    def _run_command(self, command: list[str]) -> bool:
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                shell=False,
            )
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip("\r\n")
                if line:
                    self.events.put(("log", line))
            return process.wait() == 0
        except FileNotFoundError:
            self.events.put(("log", "Не удалось запустить Python/pip. Проверь установку Python."))
            return False
        except Exception as exc:
            self.events.put(("log", f"Ошибка запуска pip: {exc}"))
            return False

    def _process_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "log":
                    self._append_log(str(payload))
                elif event == "package_start":
                    index, total, package = payload  # type: ignore[misc]
                    self.progress_text.configure(text=f"Пакет {index}/{total}: {package}")
                    self._append_log(f"→ {package}")
                elif event == "package_done":
                    index, total, package, success = payload  # type: ignore[misc]
                    label = "УСТАНОВЛЕН" if success else "ОШИБКА"
                    self._append_log(f"{package}: {label}")
                    self.progress_text.configure(text=f"Обработано: {index} из {total}")
                elif event == "finished":
                    self._finish_task(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _finish_task(self, results: list[tuple[str, bool]]) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1)
        self.progress_state.configure(text="ЗАВЕРШЕНО", text_color=C["success"])
        succeeded = sum(1 for _, ok in results if ok)
        failed = len(results) - succeeded

        if failed == 0:
            self._set_status("ГОТОВО", "success")
            self.progress_text.configure(text=f"Установка завершена · {succeeded} пак.")
            self._append_log(f"Готово: успешно обработано {succeeded} из {len(results)}.")
        else:
            self._set_status("ЕСТЬ ОШИБКИ", "danger")
            self.progress_text.configure(text=f"Готово с ошибками · {failed} не удалось")
            self._append_log(f"Результат: {succeeded} успешно, {failed} с ошибкой.")

        self._set_busy(False)
        self.package_entry.focus_set()

    def _on_close(self) -> None:
        self.destroy()


def export_brand_icons(output_dir: Path | None = None) -> tuple[Path, Path, Path]:
    """Export the embedded PIPROOM mark as PNG, ICO and ICNS build assets."""
    folder = output_dir or Path.cwd()
    folder.mkdir(parents=True, exist_ok=True)
    image = PyLibraryManager._make_logo_pil(1024)

    png_path = folder / "piproom-icon.png"
    ico_path = folder / "piproom.ico"
    icns_path = folder / "piproom.icns"

    image.save(png_path, format="PNG", optimize=True)
    image.save(ico_path, format="ICO", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
        (128, 128), (256, 256),
    ])

    # ICNS is a simple container of typed image chunks. PNG-backed entries are
    # supported by modern macOS and accepted by PyInstaller as the app-bundle icon.
    icns_entries = (("icp4", 16), ("icp5", 32), ("icp6", 64),
                    ("ic07", 128), ("ic08", 256), ("ic09", 512), ("ic10", 1024))
    chunks: list[bytes] = []
    for chunk_type, size in icns_entries:
        buffer = io.BytesIO()
        image.resize((size, size), Image.Resampling.LANCZOS).save(
            buffer, format="PNG", optimize=True
        )
        png_data = buffer.getvalue()
        chunks.append(chunk_type.encode("ascii") + struct.pack(">I", len(png_data) + 8) + png_data)
    payload = b"".join(chunks)
    icns_path.write_bytes(b"icns" + struct.pack(">I", len(payload) + 8) + payload)
    return png_path, ico_path, icns_path


def main() -> None:
    if "--export-icons" in sys.argv:
        png_path, ico_path, icns_path = export_brand_icons()
        print("PIPROOM icon files created:")
        print(f"  PNG:  {png_path}")
        print(f"  ICO:  {ico_path}")
        print(f"  ICNS: {icns_path}")
        return

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = PyLibraryManager()
    app.mainloop()


if __name__ == "__main__":
    main()
