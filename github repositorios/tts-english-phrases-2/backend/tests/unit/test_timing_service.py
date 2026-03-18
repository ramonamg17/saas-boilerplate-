"""
Unit tests for services/timing_service.py
File I/O is isolated via monkeypatching DATA_FILE to a tmp_path.
"""
import pytest
import services.timing_service as timing_module
from services.timing_service import get_estimate, save_timing, DEFAULT_ESTIMATES


def test_get_estimate_returns_default_when_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(timing_module, "DATA_FILE", tmp_path / "timing_data.json")
    assert get_estimate(5) == DEFAULT_ESTIMATES[5]
    assert get_estimate(10) == DEFAULT_ESTIMATES[10]
    assert get_estimate(30) == DEFAULT_ESTIMATES[30]


def test_get_estimate_returns_300_for_unknown_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(timing_module, "DATA_FILE", tmp_path / "timing_data.json")
    assert get_estimate(99) == 300


def test_save_and_retrieve_timing_updates_average(tmp_path, monkeypatch):
    monkeypatch.setattr(timing_module, "DATA_FILE", tmp_path / "timing_data.json")
    save_timing(10, 300.0)
    assert get_estimate(10) == 300

    save_timing(10, 400.0)
    # rolling average of 300 and 400 = 350
    assert get_estimate(10) == 350


def test_estimate_persists_across_load_calls(tmp_path, monkeypatch):
    data_file = tmp_path / "timing_data.json"
    monkeypatch.setattr(timing_module, "DATA_FILE", data_file)

    save_timing(5, 180.0)

    # Simulate a new "process" by calling get_estimate (reads from disk)
    result = get_estimate(5)
    assert result == 180

    # File must exist on disk
    assert data_file.exists()


def test_rolling_average_correct_after_multiple_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(timing_module, "DATA_FILE", tmp_path / "timing_data.json")
    save_timing(15, 600.0)
    save_timing(15, 300.0)
    save_timing(15, 600.0)
    # (600 + 300 + 600) / 3 = 500
    assert get_estimate(15) == 500


def test_different_durations_stored_independently(tmp_path, monkeypatch):
    monkeypatch.setattr(timing_module, "DATA_FILE", tmp_path / "timing_data.json")
    save_timing(5, 120.0)
    save_timing(10, 240.0)
    assert get_estimate(5) == 120
    assert get_estimate(10) == 240
