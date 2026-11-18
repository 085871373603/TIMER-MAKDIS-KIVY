"""Android foreground service: keeps countdown deadline and alarm alive in background."""
from __future__ import annotations

import os
import sys
import time
import traceback

# python-for-android exposes this variable for service processes.
SERVICE_ARGUMENT = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")


def _log(message: str) -> None:
    try:
        from jnius import autoclass
        Log = autoclass("android.util.Log")
        Log.i("TIMER_MAXDIS_SERVICE", str(message))
    except Exception:
        print("TIMER_MAXDIS_SERVICE:", message, flush=True)


def _state_path() -> str:
    from jnius import autoclass
    PythonService = autoclass("org.kivy.android.PythonService")
    context = PythonService.mService
    if context is None:
        raise RuntimeError("PythonService context belum tersedia")
    return str(context.getFilesDir().getAbsolutePath()) + "/timermaxdis_state.json"


def _create_media_player(path: str):
    from jnius import autoclass
    MediaPlayer = autoclass("android.media.MediaPlayer")
    AudioManager = autoclass("android.media.AudioManager")
    player = MediaPlayer()
    player.setAudioStreamType(AudioManager.STREAM_ALARM)
    player.setDataSource(path)
    player.setLooping(True)
    player.prepare()
    player.start()
    return player


def _stop_player(player) -> None:
    if player is None:
        return
    try:
        if player.isPlaying():
            player.stop()
    except Exception:
        pass
    try:
        player.release()
    except Exception:
        pass


def _wake_lock(context):
    from jnius import autoclass
    PowerManager = autoclass("android.os.PowerManager")
    Context = autoclass("android.content.Context")
    manager = context.getSystemService(Context.POWER_SERVICE)
    lock = manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TIMERMAXDIS:Countdown")
    lock.setReferenceCounted(False)
    return lock


def main():
    from jnius import autoclass
    from timer_logic import load_state, save_state, finish_timer, remaining_seconds

    PythonService = autoclass("org.kivy.android.PythonService")
    context = PythonService.mService
    if context is None:
        raise RuntimeError("Service context null")

    # Android may restart a sticky service after reclaiming its process.
    try:
        PythonService.mService.setAutoRestartService(True)
    except Exception as exc:
        _log("AutoRestartService unavailable: " + str(exc))

    state_file = _state_path()
    audio_file = os.path.join(str(context.getFilesDir().getAbsolutePath()), "notifikasi.mp3")
    wake = _wake_lock(context)
    player = None
    wake_held = False
    _log("Service started")

    try:
        while True:
            state = load_state(state_file)

            if not state.get("service_active"):
                try:
                    PythonService.mService.setAutoRestartService(False)
                except Exception:
                    pass
                break

            active = bool(state.get("timer_active"))
            alarm = bool(state.get("alarm_active"))

            # Keep CPU awake only for the live countdown; release it while waiting or alarming.
            if active and not wake_held:
                try:
                    wake.acquire()
                    wake_held = True
                except Exception as exc:
                    _log("WakeLock acquire failed: " + str(exc))
            elif not active and wake_held:
                try:
                    wake.release()
                except Exception:
                    pass
                wake_held = False

            if active and remaining_seconds(state, int(time.time() * 1000)) <= 0:
                if finish_timer(state, int(time.time() * 1000)):
                    save_state(state_file, state)
                    _log("Timer finished; alarm activated")
                state = load_state(state_file)
                alarm = bool(state.get("alarm_active"))
                active = False

            if alarm and player is None:
                if os.path.isfile(audio_file):
                    try:
                        player = _create_media_player(audio_file)
                        _log("Alarm MP3 playing")
                    except Exception as exc:
                        _log("MediaPlayer error: " + str(exc))
                else:
                    _log("notifikasi.mp3 not found: " + audio_file)
            elif not alarm and player is not None:
                _stop_player(player)
                player = None

            time.sleep(0.35 if active else 0.8)

    except Exception:
        _log(traceback.format_exc())
        raise
    finally:
        _stop_player(player)
        if wake_held:
            try:
                wake.release()
            except Exception:
                pass
        _log("Service stopped")


if __name__ == "__main__":
    main()
