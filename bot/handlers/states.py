"""FSM states for the track-creation dialog."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class TrackSetup(StatesGroup):
    configuring = State()
    waiting_for_target_price = State()
    waiting_for_drop_percent = State()
    waiting_for_rise_percent = State()
