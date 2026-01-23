"""
Sound Service - Controls PipeWire/PulseAudio with shell commands.
"""
import subprocess
import json
from typing import Optional


def _run_pactl(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["pactl"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_default_sink() -> Optional[str]:
    success, output = _run_pactl(["get-default-sink"])
    return output if success else None


def get_volume() -> int:
    success, output = _run_pactl(["get-sink-volume", "@DEFAULT_SINK@"]) 
    if success and output:
        try:
            for part in output.split("/"):
                if "%" in part:
                    return int(part.strip().replace("%", ""))
        except ValueError:
            pass
    return 0


def set_volume(volume: int) -> bool:
    volume = max(0, min(100, volume))
    success, _ = _run_pactl(["set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"])
    return success


def get_mute() -> bool:
    success, output = _run_pactl(["get-sink-mute", "@DEFAULT_SINK@"])
    return success and "yes" in output.lower()


def set_mute(muted: bool) -> bool:
    value = "1" if muted else "0"
    success, _ = _run_pactl(["set-sink-mute", "@DEFAULT_SINK@", value])
    return success


def toggle_mute() -> bool:
    success, _ = _run_pactl(["set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    return success


def get_output_devices() -> list[dict]:
    success, output = _run_pactl(["-f", "json", "list", "sinks"])
    if not success or not output:
        return []

    try:
        sinks = json.loads(output)
        default_sink = get_default_sink()
        devices = []

        for sink in sinks:
            volume_info = sink.get("volume", {})
            front_left = volume_info.get("front-left", {})
            volume_str = front_left.get("value_percent", "0%")

            try:
                volume = int(volume_str.replace("%", ""))
            except (ValueError, AttributeError):
                volume = 0

            devices.append(
                {
                    "name": sink.get("name", ""),
                    "description": sink.get("description", "Unknown Device"),
                    "is_default": sink.get("name") == default_sink,
                    "volume": volume,
                    "muted": sink.get("mute", False),
                }
            )

        return devices
    except (json.JSONDecodeError, KeyError):
        return []


def set_default_sink(sink_name: str) -> bool:
    success, _ = _run_pactl(["set-default-sink", sink_name])
    return success


def get_sound_status() -> dict:
    return {
        "volume": get_volume(),
        "muted": get_mute(),
        "default_sink": get_default_sink(),
        "devices": get_output_devices(),
    }
