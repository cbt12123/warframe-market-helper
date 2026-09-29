from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable


def normalize(text: str) -> str:
    """归一化：小写、去空格/下划线/连字符/点。用于检索匹配。"""
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = re.sub(r"[\s_\-·・.,/\\'\"()【】\[\]]+", "", text)
    return text


@dataclass
class Item:
    """物品（来自 /v2/items 的最小可用视图）。"""

    id: str
    slug: str
    name_en: str
    name_zh: str
    tags: list[str] = field(default_factory=list)
    ducats: int | None = None
    max_rank: int | None = None
    max_charges: int | None = None
    subtypes: list[str] = field(default_factory=list)
    vaulted: bool | None = None
    set_root: bool = False
    set_parts: list[str] = field(default_factory=list)
    icon: str | None = None
    words: list[str] = field(default_factory=list)  # slug 分词，用于词元匹配

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Item":
        i18n = raw.get("i18n") or {}
        en = (i18n.get("en") or {}) if isinstance(i18n, dict) else {}
        zh = (i18n.get("zh-hans") or i18n.get("zh") or {}) if isinstance(i18n, dict) else {}
        name_en = en.get("name") or raw.get("slug", "").replace("_", " ")
        name_zh = zh.get("name") or name_en
        slug = raw.get("slug", "")
        return cls(
            id=raw.get("id", ""),
            slug=slug,
            words=[w for w in slug.split("_") if w],
            name_en=name_en,
            name_zh=name_zh,
            tags=list(raw.get("tags") or []),
            ducats=raw.get("ducats"),
            max_rank=raw.get("maxRank"),
            max_charges=raw.get("maxCharges"),
            subtypes=list(raw.get("subtypes") or []),
            vaulted=raw.get("vaulted"),
            set_root=bool(raw.get("setRoot")),
            set_parts=list(raw.get("setParts") or []),
            icon=(en.get("thumb") or en.get("icon")),
        )

    # 归一化后的检索键
    @property
    def key_slug(self) -> str:
        return normalize(self.slug)

    @property
    def key_en(self) -> str:
        return normalize(self.name_en)

    @property
    def key_zh(self) -> str:
        return normalize(self.name_zh)

    @property
    def display(self) -> str:
        """展示名：中文名 + 英文原名。"""
        if self.name_zh and self.name_zh != self.name_en:
            return f"{self.name_zh} / {self.name_en}"
        return self.name_en

    def is_set(self) -> bool:
        return "set" in self.tags

    def is_prime(self) -> bool:
        return "prime" in self.tags


class ItemIndex:
    """物品索引：按归一化键检索。"""

    def __init__(self, items: Iterable[Item]) -> None:
        self.items: list[Item] = list(items)
        self.by_slug: dict[str, Item] = {i.slug: i for i in self.items}
        self.by_id: dict[str, Item] = {i.id: i for i in self.items}
        self._by_key: dict[str, Item] = {}
        for item in self.items:
            self._by_key.setdefault(item.key_slug, item)
            self._by_key.setdefault(item.key_en, item)
            self._by_key.setdefault(item.key_zh, item)

    def __len__(self) -> int:
        return len(self.items)

    @classmethod
    def from_api(cls, raw_items: list[dict[str, Any]]) -> "ItemIndex":
        return cls(Item.from_api(x) for x in raw_items)

    def exact(self, key: str) -> Item | None:
        return self._by_key.get(normalize(key))

    def by_slug_name(self, slug: str) -> Item | None:
        return self.by_slug.get(slug)
