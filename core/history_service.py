"""Price-history chart generation (matplotlib -> PNG bytes)."""

from __future__ import annotations

import io
import os
import tempfile

# Ensure matplotlib has a writable cache dir (headless / container / read-only home).
_MPL_CACHE = os.path.join(tempfile.gettempdir(), "market_tracker_mpl")
os.makedirs(_MPL_CACHE, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", _MPL_CACHE)

import matplotlib

matplotlib.use("Agg")  # headless backend, no display required

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from db.models import PriceHistory  # noqa: E402


def build_price_chart(history: list[PriceHistory], title: str) -> io.BytesIO:
    """Build a PNG line chart for the given history (chronological order)."""
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    dates = [h.timestamp for h in history]
    prices = [h.price for h in history]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    ax.plot(dates, prices, marker="o", markersize=4, linewidth=2, color="#2f81f7")
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlabel("Дата")
    ax.set_ylabel("Цена, ₽")
    ax.grid(True, linestyle="--", alpha=0.5)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", " ")))
    fig.autofmt_xdate(rotation=30)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer
