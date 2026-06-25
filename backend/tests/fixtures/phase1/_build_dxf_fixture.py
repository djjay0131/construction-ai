"""Builder for ``dxf_smoketest_4wall.dxf`` — a 16'x16' rectangle of 4 walls.

Run once; commit the output. Re-run only if the fixture spec changes.

    $ uv run python backend/tests/fixtures/phase1/_build_dxf_fixture.py
"""

from __future__ import annotations
from pathlib import Path

import ezdxf

OUTPUT = Path(__file__).resolve().parent / "dxf_smoketest_4wall.dxf"


def build() -> Path:
    doc = ezdxf.new()
    msp = doc.modelspace()
    # 16' x 16' rectangle in DXF inches (16 ft = 192 in)
    msp.add_line((0, 0), (192, 0))
    msp.add_line((192, 0), (192, 192))
    msp.add_line((192, 192), (0, 192))
    msp.add_line((0, 192), (0, 0))
    doc.saveas(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":  # pragma: no cover - one-shot CLI
    out = build()
    print(f"wrote {out}")
