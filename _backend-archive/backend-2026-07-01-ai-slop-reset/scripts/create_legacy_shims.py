"""Generate orchestrator/telephony shim packages pointing at legacy/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = '"""Compatibility shim — implementation in legacy.{pkg}."""\n'


def make_shim(target: Path, legacy_mod: str, pkg: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        HEADER.format(pkg=pkg) + f"from {legacy_mod} import *  # noqa: F401,F403\n",
        encoding="utf-8",
    )


def main() -> None:
    orch = ROOT / "legacy" / "orchestrator"
    for py in orch.glob("*.py"):
        if py.name == "__init__.py":
            continue
        make_shim(ROOT / "orchestrator" / py.name, f"legacy.orchestrator.{py.stem}", "orchestrator")

    (ROOT / "orchestrator" / "__init__.py").write_text(
        HEADER.format(pkg="orchestrator") + "from legacy.orchestrator import *  # noqa: F401,F403\n",
        encoding="utf-8",
    )

    tel_root = ROOT / "legacy" / "telephony"
    for py in tel_root.rglob("*.py"):
        rel = py.relative_to(tel_root)
        if rel.name == "__init__.py" and rel.parent == Path("."):
            mod = "legacy.telephony"
        else:
            parts = list(rel.with_suffix("").parts)
            mod = "legacy.telephony." + ".".join(parts)
        make_shim(ROOT / "telephony" / rel, mod, "telephony")

    print("shims ok")


if __name__ == "__main__":
    main()