"""Load A's versioned method assets without replacing the legacy library."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .criteria import CriteriaLibrary
from .errors import EngineError

ROOT = Path(__file__).resolve().parent.parent
METHOD_ROOT = ROOT / "方法专家开发交付-v0.2"
METHOD_FILES = (
    "00先看这个！！！！-阅读与开发交接.md",
    "01-04-场景输入流程与技术路径.md",
    "05-24条判据修订与变更对照.md",
    "05-判据库-v0.2.json",
    "05-判据执行补充-v0.2.json",
    "05-逐字段变更对照.csv",
    "06-新场景方法-v0.2.json",
    "06-新场景方法与正反例.md",
    "07-会话变更重查与复审规则.md",
    "08-问题表达严重度与评价验收.md",
    "09-开发验收用例.json",
    "09-开发验收用例.md",
    "10-来源索引.json",
    "11-交付校验结果.json",
)


class MethodRegistry:
    def __init__(self, root: Path = METHOD_ROOT) -> None:
        self.root = root
        self.criteria = CriteriaLibrary.load(root / "05-判据库-v0.2.json")
        try:
            supplement = self._read("05-判据执行补充-v0.2.json")
            methods = self._read("06-新场景方法-v0.2.json")
            self.supplements = {row["rule_id"]: row for row in supplement["rules"]}
            self.methods = {row["id"]: row for row in methods["methods"]}
            self.delivery_validation = self._validate_delivery()
            if len(self.supplements) != 24 or set(self.supplements) != set(self.criteria.rule_ids):
                raise ValueError("Execution supplements must cover exactly R01-R24.")
            if set(self.methods) != {f"E{i:02}" for i in range(1, 9)}:
                raise ValueError("Expected E01-E08.")
            if supplement["version"] != self.version or methods["version"] != self.version:
                raise ValueError("Method asset versions differ.")
            for method in self.methods.values():
                for field in ("title", "object", "context", "applies", "steps", "evidence", "mark", "abstain"):
                    if not method.get(field):
                        raise ValueError(f"{method['id']} missing {field}")
                if not set(method["related"]).issubset(self.criteria.rule_ids):
                    raise ValueError("Unknown method reference.")
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise EngineError("method_assets_invalid", str(exc), status_code=503) from exc

    def _read(self, name: str) -> dict[str, Any]:
        return json.loads((self.root / name).read_text(encoding="utf-8-sig"))

    def _validate_delivery(self) -> dict[str, Any]:
        manifest = self._read("11-交付校验结果.json")
        checked = 0
        mismatches = []
        for item in manifest.get("files", []):
            path = self.root / item["path"]
            if not path.is_file():
                continue
            checked += 1
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != item.get("sha256"):
                mismatches.append({
                    "path": item["path"],
                    "declared": item.get("sha256"),
                    "actual": actual,
                })
        if mismatches:
            raise EngineError(
                "method_delivery_hash_mismatch",
                f"A method delivery contains {len(mismatches)} modified file(s).",
                status_code=503,
                details={"mismatches": mismatches},
            )
        return {
            "delivery_version": manifest.get("delivery_version"),
            "checked_files": checked,
            "mismatches": 0,
        }

    @property
    def version(self) -> str:
        return self.criteria.version

    @property
    def refs(self) -> list[str]:
        return [*self.criteria.rule_ids, *self.methods]

    def spec(self, ref: str) -> dict[str, Any]:
        if ref in self.criteria.by_id:
            return {
                **self.criteria.by_id[ref].model_dump(),
                "execution": self.supplements[ref],
                "source": self.criteria.source.model_dump(),
            }
        if ref in self.methods:
            return self.methods[ref]
        raise EngineError("unknown_check_ref", f"Unknown method: {ref}", status_code=422)

    def fingerprints(self) -> dict[str, str]:
        return {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in METHOD_FILES if (self.root / name).is_file()
        }
