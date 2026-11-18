"""TIMER MAXDIS - Kivy Android client UI."""
from __future__ import annotations

import os
import shutil
import time
import webbrowser
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Line

from timer_logic import (
    LORENGS,
    new_state,
    load_state,
    save_state,
    start_timer,
    advance_lorong,
    calculate_result,
    finish_timer,
    format_duration,
    remaining_seconds,
)

APP_URL = "https://apktoko.arinex.my.id/menu.html"
RED = (0.90, 0.08, 0.12, 1)
BLUE = (0.00, 0.34, 0.62, 1)
DARK = (0.12, 0.15, 0.19, 1)
GREY = (0.43, 0.47, 0.53, 1)
LIGHT = (0.96, 0.97, 0.98, 1)
GREEN = (0.17, 0.60, 0.32, 1)


def wall_ms() -> int:
    return int(time.time() * 1000)


def android_files_dir() -> str:
    """Use the same app-private files directory from Activity and Service."""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        return str(activity.getFilesDir().getAbsolutePath())
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".timer_maxdis")


def start_android_service(state: dict) -> bool:
    try:
        from jnius import autoclass
        service_class = autoclass("id.arinex.timermaxdis.ServiceTimer")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        index = min(max(int(state.get("current_index", 0)), 0), 5)
        code = LORENGS[index]["code"]
        content = "RUNNING • HITUNG MUNDUR DI LATAR BELAKANG"
        # The custom small icon is packaged as Android drawable ic_stat_maxdis.
        service_class.start(
            activity,
            "ic_stat_maxdis",
            "TIMER MAXDIS",
            content,
            "",
        )
        return True
    except Exception as exc:
        print("Foreground service start failed:", exc)
        return False


class ProgressRing(Widget):
    progress = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw, progress=self.redraw)
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        radius = max(dp(12), min(self.width, self.height) / 2 - dp(9))
        with self.canvas:
            Color(0.88, 0.90, 0.92, 1)
            Line(circle=(cx, cy, radius), width=dp(9), segments=100)
            value = max(0.0, min(1.0, float(self.progress)))
            if value > 0:
                from math import cos, sin, pi
                points = []
                steps = max(2, int(120 * value))
                for i in range(steps + 1):
                    angle = (-pi / 2) + (2 * pi * value * i / steps)
                    points.extend((cx + radius * cos(angle), cy + radius * sin(angle)))
                Color(*RED)
                Line(points=points, width=dp(9))


class MaxdisApp(App):
    def build(self):
        self.title = "TIMER MAXDIS"
        self.icon = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        Window.clearcolor = LIGHT
        self.state_path = os.path.join(android_files_dir(), "timermaxdis_state.json")
        self.audio_path = os.path.join(android_files_dir(), "notifikasi.mp3")
        self.state = load_state(self.state_path)
        self.timer_modal = None
        self.result_modal = None
        self._last_modal_state = None
        self._desktop_audio_event = None
        self._last_list_signature = None

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        header = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(10))
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        header.add_widget(Image(source=logo_path, size_hint=(None, 1), width=dp(54), allow_stretch=True))
        title_box = BoxLayout(orientation="vertical", spacing=dp(1))
        title_box.add_widget(Label(text="TIMER MAXDIS", bold=True, color=DARK, font_size="19sp", halign="left", valign="middle"))
        title_box.add_widget(Label(text="TIMER PENGISIAN LORONG", color=GREY, font_size="10sp", halign="left", valign="top"))
        header.add_widget(title_box)
        menu_btn = Button(text="MENU", size_hint=(None, None), size=(dp(78), dp(42)), bold=True,
                          background_normal="", background_color=RED, color=(1, 1, 1, 1))
        menu_btn.bind(on_release=self.open_menu)
        header.add_widget(menu_btn)
        root.add_widget(header)

        stepper = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        self.step_labels = []
        for number, label in [("1", "INPUT"), ("2", "PROSES"), ("3", "SELESAI")]:
            item = BoxLayout(orientation="vertical", spacing=0)
            lbl = Label(text=f"{number}  {label}", bold=True, font_size="12sp", color=BLUE if number == "1" else GREY)
            item.add_widget(lbl)
            self.step_labels.append(lbl)
            stepper.add_widget(item)
        root.add_widget(stepper)

        info = Label(
            text="Masukkan QTY lalu tekan ENTER untuk memulai timer.\nRumus: (Qty / 12) × 60 detik.",
            size_hint_y=None, height=dp(54), color=DARK, font_size="12sp", halign="center", valign="middle"
        )
        info.bind(size=lambda inst, value: setattr(inst, "text_size", value))
        root.add_widget(info)

        list_header = BoxLayout(size_hint_y=None, height=dp(38), padding=(dp(12), 0, dp(10), 0), spacing=dp(8))
        list_header.add_widget(Label(text="DETAIL LORONG", color=(1, 1, 1, 1), bold=True, halign="left"))
        list_header.add_widget(Label(text="QTY", color=(1, 1, 1, 1), bold=True, size_hint_x=None, width=dp(75)))
        list_header.add_widget(Label(text="STATUS", color=(1, 1, 1, 1), bold=True, size_hint_x=None, width=dp(55)))
        list_header.canvas.before.clear()
        with list_header.canvas.before:
            Color(*RED)
            from kivy.graphics import Rectangle
            list_header._bg = Rectangle(pos=list_header.pos, size=list_header.size)
        list_header.bind(pos=lambda w, p: setattr(list_header._bg, "pos", p), size=lambda w, s: setattr(list_header._bg, "size", s))
        root.add_widget(list_header)

        scroll = ScrollView(do_scroll_x=False)
        self.rows_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.rows_box.bind(minimum_height=self.rows_box.setter("height"))
        scroll.add_widget(self.rows_box)
        root.add_widget(scroll)

        self.footer = Label(text="OFFLINE READY  •  TIMER MAXDIS", size_hint_y=None, height=dp(28), color=GREY, font_size="10sp")
        root.add_widget(self.footer)
        self.root_layout = root
        self.refresh_list()
        return root

    def on_start(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self._copy_alarm_asset()
        self.state = load_state(self.state_path)
        if self.state.get("service_active"):
            start_android_service(self.state)
        self._request_notification_permission()
        Clock.schedule_interval(self.poll_state, 0.20)
        Clock.schedule_once(lambda *_: self.restore_ui(), 0.25)

    def on_pause(self):
        # Returning True keeps Kivy's activity pause lifecycle; the Android foreground service owns the timer.
        return True

    def on_resume(self):
        self.state = load_state(self.state_path)
        if self.state.get("service_active"):
            start_android_service(self.state)
        Clock.schedule_once(lambda *_: self.restore_ui(), 0.15)

    def _request_notification_permission(self):
        try:
            from android.permissions import request_permissions
            from jnius import autoclass
            AndroidVersion = autoclass("android.os.Build$VERSION")
            if int(AndroidVersion.SDK_INT) >= 33:
                request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except Exception:
            # Older Android versions or desktop builds do not expose the runtime permission module.
            pass

    def _copy_alarm_asset(self):
        source = os.path.join(os.path.dirname(__file__), "assets", "notifikasi.mp3")
        if os.path.isfile(source):
            try:
                if not os.path.isfile(self.audio_path) or os.path.getsize(self.audio_path) != os.path.getsize(source):
                    shutil.copy2(source, self.audio_path)
            except OSError as exc:
                print("Cannot copy alarm asset:", exc)

    def persist(self):
        save_state(self.state_path, self.state)

    def refresh_list(self):
        self.rows_box.clear_widgets()
        self._last_list_signature = (int(self.state.get("current_index", 0)), tuple(self.state.get("qty_history", [])), tuple(self.state.get("completed", [])), bool(self.state.get("timer_active")))
        index = int(self.state.get("current_index", 0))
        qty_values = self.state.get("qty_history", [None] * 6)
        done_values = self.state.get("completed", [False] * 6)
        for i, item in enumerate(LORENGS):
            row = BoxLayout(size_hint_y=None, height=dp(58), padding=(dp(10), dp(4)), spacing=dp(8))
            info = BoxLayout(orientation="vertical", spacing=0)
            code_label = Label(text=item["code"], color=GREY, font_size="10sp", halign="left", valign="bottom")
            code_label.bind(size=lambda w, size: setattr(w, "text_size", size))
            name_label = Label(text=item["name"], color=DARK, bold=True, font_size="13sp", halign="left", valign="top")
            name_label.bind(size=lambda w, size: setattr(w, "text_size", size))
            info.add_widget(code_label)
            info.add_widget(name_label)
            row.add_widget(info)
            qty = TextInput(text="" if qty_values[i] is None else str(qty_values[i]), hint_text="0", multiline=False,
                            input_filter="int", size_hint=(None, None), size=(dp(75), dp(40)), halign="center",
                            font_size="16sp", disabled=(i != index or bool(self.state.get("timer_active")) or bool(done_values[i])))
            qty.bind(on_text_validate=lambda widget, ix=i: self.on_qty_entered(ix, widget.text))
            row.add_widget(qty)
            status = "✓" if done_values[i] else ("●" if i == index else "")
            status_color = GREEN if done_values[i] else (BLUE if i == index else GREY)
            row.add_widget(Label(text=status, color=status_color, bold=True, size_hint=(None, 1), width=dp(55), font_size="20sp"))
            # Alternating row surfaces improve readability on a small screen.
            with row.canvas.before:
                Color(0.91, 0.95, 0.98, 1) if i == index else Color(1, 1, 1, 1)
                from kivy.graphics import Rectangle
                bg = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos=lambda w, p, r=bg: setattr(r, "pos", p), size=lambda w, s, r=bg: setattr(r, "size", s))
            self.rows_box.add_widget(row)

        if index >= 6 or self.state.get("alarm_active"):
            step = 3
        elif self.state.get("timer_active"):
            step = 2
        else:
            step = 1
        for i, label in enumerate(self.step_labels):
            label.color = GREEN if i + 1 < step else (BLUE if i + 1 == step else GREY)

    def on_qty_entered(self, index: int, raw: str):
        if index != int(self.state.get("current_index", 0)):
            return
        try:
            qty = int(raw.strip())
            self.state = start_timer(self.state, qty, wall_ms())
            self.persist()
            self.refresh_list()
            service_ok = start_android_service(self.state)
            if not service_ok:
                self.footer.text = "LATAR BELAKANG TIDAK AKTIF"
                self.show_message(
                    "LAYANAN BACKGROUND GAGAL",
                    "Timer tetap tampil, tetapi tidak dijamin berjalan saat aplikasi ditinggalkan. Periksa izin notifikasi dan instalasi APK.",
                )
            self.show_timer_modal()
        except (ValueError, TypeError) as exc:
            self.show_message("QTY TIDAK VALID", str(exc))

    def show_timer_modal(self):
        if self.timer_modal is None:
            modal = ModalView(size_hint=(0.92, 0.76), auto_dismiss=False, background_color=(0, 0, 0, 0.55))
            card = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(8))
            with card.canvas.before:
                Color(1, 1, 1, 1)
                from kivy.graphics import RoundedRectangle
                card_bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(22)] * 4)
            card.bind(pos=lambda w, p: setattr(card_bg, "pos", p), size=lambda w, s: setattr(card_bg, "size", s))
            top = BoxLayout(size_hint_y=None, height=dp(32))
            self.timer_badge = Label(text="● TIMER AKTIF", color=GREEN, bold=True, halign="left")
            self.timer_qty_label = Label(text="QTY 0", color=DARK, bold=True, halign="right")
            top.add_widget(self.timer_badge)
            top.add_widget(self.timer_qty_label)
            card.add_widget(top)
            self.timer_title = Label(text="LORONG 1", color=DARK, bold=True, font_size="24sp", size_hint_y=None, height=dp(38))
            card.add_widget(self.timer_title)
            ring_wrap = BoxLayout(orientation="vertical", size_hint=(1, 1), padding=(dp(32), dp(2)))
            self.ring = ProgressRing(size_hint=(1, 1))
            self.timer_display = Label(text="00:00", color=DARK, bold=True, font_size="48sp")
            # Overlay text is centered over the custom progress ring.
            self.ring_holder = FloatLayout()
            self.ring.size_hint = (0.82, 0.82)
            self.ring.pos_hint = {"center_x": 0.5, "center_y": 0.5}
            self.timer_display.size_hint = (0.72, 0.30)
            self.timer_display.pos_hint = {"center_x": 0.5, "center_y": 0.5}
            self.ring_holder.add_widget(self.ring)
            self.ring_holder.add_widget(self.timer_display)
            ring_wrap.add_widget(self.ring_holder)
            card.add_widget(ring_wrap)
            self.timer_message = Label(text="Waktu berjalan.", color=GREY, font_size="14sp", size_hint_y=None, height=dp(42))
            card.add_widget(self.timer_message)
            self.next_button = Button(text="LANJUT LORONG BERIKUTNYA", size_hint_y=None, height=dp(48), bold=True,
                                      background_normal="", background_color=RED, color=(1, 1, 1, 1), opacity=0, disabled=True)
            self.next_button.bind(on_release=self.next_lorong)
            card.add_widget(self.next_button)
            modal.add_widget(card)
            self.timer_modal = modal
        self.update_timer_view()
        if not self.timer_modal.parent:
            self.timer_modal.open()

    def update_timer_view(self):
        if self.timer_modal is None:
            return
        index = min(max(int(self.state.get("current_index", 0)), 0), 5)
        self.timer_title.text = LORENGS[index]["name"]
        self.timer_qty_label.text = f"QTY {self.state.get('current_qty', 0)}"
        if self.state.get("timer_active"):
            seconds = remaining_seconds(self.state, wall_ms())
            total = max(1, int(self.state.get("timer_total_seconds", 1)))
            self.timer_display.text = format_duration(seconds)
            self.ring.progress = seconds / total
            self.timer_message.text = "Hampir selesai!" if seconds <= 10 else "Waktu berjalan."
            self.timer_badge.text = "● TIMER AKTIF"
            self.next_button.opacity = 0
            self.next_button.disabled = True
            self.next_button.height = 0
        elif self.state.get("alarm_active"):
            self.timer_display.text = "00:00"
            self.ring.progress = 0
            self.timer_message.text = "WAKTU HABIS! Tekan tombol untuk melanjutkan."
            self.timer_badge.text = "● SELESAI"
            self.next_button.opacity = 1
            self.next_button.disabled = False
            self.next_button.height = dp(48)

    def next_lorong(self, *_):
        try:
            all_done = advance_lorong(self.state)
            self.persist()
            if self.timer_modal:
                self.timer_modal.dismiss()
            self.timer_modal = None
            if all_done:
                self.refresh_list()
                self.show_result()
            else:
                self.refresh_list()
        except ValueError as exc:
            self.show_message("TIDAK DAPAT MELANJUTKAN", str(exc))

    def show_result(self):
        result = self.state.get("last_result") or calculate_result(self.state)
        modal = ModalView(size_hint=(0.92, 0.82), auto_dismiss=False)
        panel = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(8))
        panel.add_widget(Label(text="SELURUH LORONG SELESAI", color=RED, bold=True, font_size="20sp", size_hint_y=None, height=dp(38)))
        panel.add_widget(Label(text=result["status"], color=GREEN if result["category"] == "good" else (0.9, 0.4, 0.05, 1) if result["category"] == "fast" else RED, bold=True, size_hint_y=None, height=dp(34)))
        values = [
            ("TOTAL QTY", f"{result['total_qty']:,}".replace(",", ".")),
            ("SHIFT", result["shift"]),
            ("WAKTU STANDAR", format_duration(result["target_seconds"])),
            ("WAKTU KERJA", format_duration(result["work_seconds"])),
            ("TOTAL GAP", format_duration(result["gap_seconds"])),
            ("WAKTU AKTUAL", format_duration(result["actual_seconds"])),
            ("DEVIASI", f"{result['deviation_percent']:+.1f}%"),
            ("WAKTU SELESAI", datetime.fromtimestamp(result["finished_at_ms"] / 1000).strftime("%d/%m/%Y %H:%M:%S") if result["finished_at_ms"] else "-"),
        ]
        grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=1)
        for label, value in values:
            grid.add_widget(Label(text=f"{label}\n[b]{value}[/b]", markup=True, color=DARK, font_size="12sp", halign="center"))
        panel.add_widget(grid)
        ok = Button(text="OK • MULAI SESI BARU", size_hint_y=None, height=dp(48), background_normal="", background_color=RED, color=(1, 1, 1, 1), bold=True)
        ok.bind(on_release=lambda *_: self.reset_session(modal))
        panel.add_widget(ok)
        modal.add_widget(panel)
        self.result_modal = modal
        modal.open()

    def reset_session(self, modal):
        modal.dismiss()
        self.state = new_state()
        self.persist()
        self.refresh_list()
        self.footer.text = "OFFLINE READY  •  TIMER MAXDIS"

    def poll_state(self, _dt):
        fresh = load_state(self.state_path)
        # Desktop-only fallback for UI development; Android uses the foreground service process.
        if platform != "android" and fresh.get("timer_active") and remaining_seconds(fresh, wall_ms()) <= 0:
            if finish_timer(fresh, wall_ms()):
                save_state(self.state_path, fresh)
        self.state = fresh
        if self.timer_modal and self.timer_modal.parent:
            if fresh.get("timer_active") or fresh.get("alarm_active"):
                self.update_timer_view()
            else:
                self.timer_modal.dismiss()
                self.timer_modal = None
        elif fresh.get("timer_active") or fresh.get("alarm_active"):
            self.show_timer_modal()
        if int(fresh.get("current_index", 0)) >= 6 and fresh.get("last_result") and (self.result_modal is None or not self.result_modal.parent):
            self.show_result()
        signature = (int(fresh.get("current_index", 0)), tuple(fresh.get("qty_history", [])), tuple(fresh.get("completed", [])), bool(fresh.get("timer_active")))
        if signature != self._last_list_signature:
            self.refresh_list()

    def restore_ui(self):
        self.state = load_state(self.state_path)
        self.refresh_list()
        if self.state.get("timer_active") or self.state.get("alarm_active"):
            self.show_timer_modal()
        elif int(self.state.get("current_index", 0)) >= 6 and self.state.get("last_result"):
            self.show_result()

    def open_menu(self, *_):
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(APP_URL))
            activity.startActivity(intent)
        except Exception:
            webbrowser.open(APP_URL)

    def show_message(self, title: str, message: str):
        modal = ModalView(size_hint=(0.86, 0.32), auto_dismiss=True)
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(8))
        box.add_widget(Label(text=title, color=RED, bold=True, font_size="18sp"))
        box.add_widget(Label(text=message, color=DARK, font_size="14sp"))
        button = Button(text="OK", size_hint_y=None, height=dp(42), background_normal="", background_color=BLUE)
        button.bind(on_release=modal.dismiss)
        box.add_widget(button)
        modal.add_widget(box)
        modal.open()


if __name__ == "__main__":
    MaxdisApp().run()
