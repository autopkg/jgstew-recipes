"""Unit tests for the headless-availability guards on Notifier and TextToSpeech.

Both expose a static _*_available() that returns False on a headless Linux host
(no D-Bus session / no display) and True on macOS/Windows.
"""

import Notifier as notifier_mod
import pytest
import TextToSpeech as tts_mod

CASES = [
    (notifier_mod.Notifier, "_desktop_available"),
    (tts_mod.TextToSpeech, "_speech_available"),
]


@pytest.mark.parametrize("cls, method_name", CASES)
def test_available_true_on_macos(monkeypatch, cls, method_name):
    module = __import__(cls.__module__)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    assert getattr(cls, method_name)() is True


@pytest.mark.parametrize("cls, method_name", CASES)
def test_available_true_on_windows(monkeypatch, cls, method_name):
    module = __import__(cls.__module__)
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    assert getattr(cls, method_name)() is True


@pytest.mark.parametrize("cls, method_name", CASES)
def test_available_false_on_headless_linux(monkeypatch, cls, method_name):
    module = __import__(cls.__module__)
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    assert getattr(cls, method_name)() is False


@pytest.mark.parametrize("cls, method_name", CASES)
def test_available_true_on_linux_with_display(monkeypatch, cls, method_name):
    module = __import__(cls.__module__)
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    assert getattr(cls, method_name)() is True
