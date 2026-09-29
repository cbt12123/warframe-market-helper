from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from .items import Item, ItemIndex, normalize

_RANK_RE = re.compile(r"(?:r|rank|等级)\s*(\d{1,2})$", re.IGNORECASE)

DEFAULT_ALIASES = Path(__file__).resolve().parents[1] / "data" / "aliases.yaml"


@dataclass
class Query:
    raw: str
    text: str            # 去掉 rank 后的主查询
    tokens: set[str]     # 别名展开后的规范词元
    literals: set[str]   # 未命中别名的原文片段
    rank: int | None = None


@dataclass
class Candidate:
    item: Item
    score: float = 0.0


class ItemSearcher:
    """中文/英文/外号混合检索。"""

    def __init__(self, index: ItemIndex, aliases: dict[str, str] | None = None) -> None:
        self.index = index
        self.aliases: dict[str, str] = {}
        if aliases is None:
            aliases = load_aliases()
        for k, v in (aliases or {}).items():
            key = normalize(str(k))
            if not key:
                continue
            val = normalize(str(v)).replace(" ", "")
            self.aliases[key] = val
        # 长键优先，避免 "p" 抢先匹配
        self._alias_keys = sorted(self.aliases, key=len, reverse=True)

    # ---------- 解析 ----------

    def parse(self, query: str) -> Query:
        raw = query.strip()
        rank = None
        text = normalize(raw)

        m = _RANK_RE.search(text)
        if m:
            rank = int(m.group(1))
            text = text[: m.start()]

        tokens: set[str] = set()
        literals: set[str] = set()
        rest = text
        i = 0
        buf = ""
        while i < len(rest):
            matched = None
            for key in self._alias_keys:
                if rest.startswith(key, i):
                    matched = key
                    break
            if matched:
                if buf:
                    literals.add(buf)
                    buf = ""
                tokens.add(self.aliases[matched])
                i += len(matched)
            else:
                buf += rest[i]
                i += 1
        if buf:
            literals.add(buf)
        # 单个字母 p 作为后缀的情况（如 "voltp"）
        if not tokens and text.endswith("p") and normalize(raw) != "p":
            pass  # 交给 literals 兜底匹配

        return Query(raw=raw, text=text, tokens=tokens, literals=literals, rank=rank)

    # ---------- 检索 ----------

    def search(self, query: str, limit: int = 8) -> list[Item]:
        q = self.parse(query)

        # 1) 整体精确命中
        exact = self.index.exact(q.text) or self.index.exact(q.raw)
        if exact:
            return [exact]

        scored: list[Candidate] = []
        for item in self.index.items:
            score = self._score(item, q)
            if score > 0:
                scored.append(Candidate(item, score))
        if not scored:
            return []
        scored.sort(key=lambda c: (-c.score, len(c.item.slug), c.item.slug))
        return [c.item for c in scored[:limit]]

    def _score(self, item: Item, q: Query) -> float:
        keys = (item.key_slug, item.key_en, item.key_zh)
        words = item.words
        score = 0.0

        # 词元必须全部命中：优先 slug 分词精确相等，其次英文单词前缀
        if q.tokens:
            if all(any(w == tok for w in words) for tok in q.tokens):
                score += 40 + 10 * len(q.tokens)
            elif all(
                any(w.startswith(tok) and len(tok) >= 4 for w in words) for tok in q.tokens
            ):
                score += 20 + 5 * len(q.tokens)
            else:
                return 0.0

        for lit in q.literals:
            if not lit:
                continue
            if any(k == lit for k in keys):
                score += 60
            elif lit in item.key_zh or lit in item.key_en:
                score += 30
            elif any(w == lit or (len(lit) >= 4 and w.startswith(lit)) for w in words):
                score += 25
            else:
                # 模糊相似度兜底
                ratio = max(
                    SequenceMatcher(None, lit, item.key_zh).ratio(),
                    SequenceMatcher(None, lit, item.key_en).ratio(),
                    SequenceMatcher(None, lit, item.key_slug).ratio(),
                )
                if ratio >= 0.75:
                    score += 10 * ratio
                else:
                    return 0.0

        if not q.tokens and not q.literals:
            return 0.0

        # 排序偏好：套装 > 散件；「圣装/p」决定 Prime 与否；名称更短优先
        if item.is_set():
            score += 6
        if "prime" in q.tokens:
            score += 5 if item.is_prime() else -5
        else:
            score += 3 if not item.is_prime() else -3
        if "blueprint" in item.tags:
            score -= 1
        score -= min(len(item.slug), 60) / 60
        return score


def load_aliases(path: Path | str | None = None) -> dict[str, str]:
    p = Path(path) if path else DEFAULT_ALIASES
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in data.items()}
