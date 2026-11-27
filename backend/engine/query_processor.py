"""
Query Understanding & Normalization Pipeline:
- Keyboard layout auto-switching (ЙЦУКЕН <-> QWERTY)
- Mixed Cyrillic-Latin homoglyph cleanup
- Multi-word & single-token phonetic/brand alias normalization
- RapidFuzz typo correction over catalog vocabulary
- Domain jargon, rebranding & slang expansion
- Hardware vs Software intent disambiguation (e.g. 'сервер') and constraint extraction
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Set, Tuple
from rapidfuzz import fuzz, process

from backend.data.build_index import fix_homoglyphs
from backend.data.domain_knowledge import (
    CANONICAL_TOKEN_ALIASES,
    DOMAIN_QUERY_RULES,
    EN_TO_RU_MAP,
    RU_TO_EN_MAP,
    SERVER_HARDWARE_TRIGGERS,
    SERVER_SOFTWARE_QUALIFIERS,
    QueryRule,
)

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-.][A-Za-zА-Яа-яЁё0-9]+)*")
_VERSION_RE = re.compile(r"\b(\d+\.\d+|202[0-6])\b")
_BUDGET_RE = re.compile(r"(?:до|не\s+дороже|бюджет)\s*(\d[\d\s]{2,10})\s*(?:тыс|к|k|р|руб|₽)?", re.IGNORECASE)
_SECONDARY_INTENT_RE = re.compile(
    r"(продлени|сертификат|техподдерж|техническ\w+\s+поддерж|обновлени|upgrade|renewal|cross-grade|миграци|обучен|курс|настройк)",
    re.IGNORECASE,
)
_RU_REGISTRY_RE = re.compile(
    r"(реестр|отечествен|импортозамещ|российск\w+\s+(?:по|аналог|софт|ос)|фстэк|еррп|минцифр|минпромторг)",
    re.IGNORECASE,
)

# Pre-sort multi-word and single-word aliases longest-first
_SORTED_ALIASES: List[Tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(rf"(?<![A-Za-zА-Яа-яЁё0-9]){re.escape(src)}(?![A-Za-zА-Яа-яЁё0-9])", re.IGNORECASE),
        src,
        dst,
    )
    for src, dst in sorted(CANONICAL_TOKEN_ALIASES.items(), key=lambda kv: -len(kv[0]))
]


@dataclass
class DisambiguationChip:
    intent_id: str
    label: str
    active: bool


@dataclass
class ProcessedQuery:
    raw_query: str
    normalized_query: str
    semantic_query: str
    lexical_tokens: List[str]
    detected_intent: str  # 'hardware' | 'software' | 'options' | 'general'
    is_server_ambiguous: bool = False
    transformations: List[str] = field(default_factory=list)
    explanation: str = ""
    matched_rule: Optional[QueryRule] = None
    wants_secondary_sku: bool = False
    wants_ru_registry: bool = False
    wants_home_business: bool = False
    requested_version: str = ""
    max_budget: Optional[float] = None
    disambiguation_chips: List[DisambiguationChip] = field(default_factory=list)


class QueryProcessor:
    def __init__(self, fuzzy_vocab: List[str]) -> None:
        self.fuzzy_vocab = fuzzy_vocab
        self.vocab_set: Set[str] = set(fuzzy_vocab)
        for src, dst in CANONICAL_TOKEN_ALIASES.items():
            for w in _TOKEN_RE.findall(src.lower()) + _TOKEN_RE.findall(dst.lower()):
                self.vocab_set.add(w)
        for rule in DOMAIN_QUERY_RULES:
            for trig in rule.triggers:
                for w in _TOKEN_RE.findall(trig.lower()):
                    self.vocab_set.add(w)

        # Bucket vocabulary by first character for sub-millisecond fuzzy correction
        self._vocab_by_first: Dict[str, List[str]] = {}
        for w in fuzzy_vocab:
            if len(w) >= 4:
                self._vocab_by_first.setdefault(w[0], []).append(w)

    def _count_known_tokens(self, text: str) -> int:
        toks = _TOKEN_RE.findall(text.lower().replace("ё", "е"))
        known = 0
        for t in toks:
            if t in self.vocab_set or t in CANONICAL_TOKEN_ALIASES:
                known += 1
        # Also check full phrase in aliases/rules
        low = text.lower().strip()
        if low in CANONICAL_TOKEN_ALIASES:
            known += 2
        for r in DOMAIN_QUERY_RULES:
            if low in r.triggers:
                known += 2
        return known

    def _maybe_fix_layout(self, q: str) -> Tuple[str, Optional[str]]:
        alpha_chars = [c for c in q if c.isalpha()]
        if len(alpha_chars) < 3:
            return q, None
        orig_known = self._count_known_tokens(q)
        if orig_known > 0:
            return q, None

        cand_ru = q.translate(EN_TO_RU_MAP)
        cand_en = q.translate(RU_TO_EN_MAP)
        ru_known = self._count_known_tokens(cand_ru)
        en_known = self._count_known_tokens(cand_en)

        if ru_known > 0 and ru_known >= en_known:
            return cand_ru, f"Исправлена раскладка клавиатуры: «{q}» → «{cand_ru}»"
        if en_known > 0:
            return cand_en, f"Исправлена раскладка клавиатуры: «{q}» → «{cand_en}»"

        # Secondary check: maybe switched layout + alias (e.g. fcnhf -> астра)
        for cand in (cand_ru, cand_en):
            aliased = self._apply_aliases(cand)[0]
            if aliased != cand or self._count_known_tokens(aliased) > 0:
                return cand, f"Исправлена раскладка клавиатуры: «{q}» → «{cand}»"
        return q, None

    def _apply_aliases(self, q: str) -> Tuple[str, List[str]]:
        notes: List[str] = []
        cur = q
        for pat, src, dst in _SORTED_ALIASES:
            if pat.search(cur):
                new_cur = pat.sub(dst, cur)
                if new_cur.lower() != cur.lower():
                    notes.append(f"Нормализация термина: «{src}» → «{dst}»")
                    cur = new_cur
        return cur, notes

    def _fix_typos(self, q: str) -> Tuple[str, List[str]]:
        notes: List[str] = []
        tokens = q.split()
        out_tokens: List[str] = []

        for raw_tok in tokens:
            clean_tok = raw_tok.lower().strip(",.;:!?()[]{}\"'").replace("ё", "е")
            if (
                len(clean_tok) < 4
                or any(ch.isdigit() for ch in clean_tok)
                or clean_tok in self.vocab_set
            ):
                out_tokens.append(raw_tok)
                continue

            # Search candidates starting with same first char (or neighbor chars for first-char typo)
            pool = self._vocab_by_first.get(clean_tok[0], [])
            if len(pool) < 30:
                pool = self.fuzzy_vocab[:4000]

            match = process.extractOne(
                clean_tok,
                pool,
                scorer=fuzz.ratio,
                score_cutoff=80.0,
            )
            if match is None and len(clean_tok) >= 5:
                match = process.extractOne(
                    clean_tok,
                    self.fuzzy_vocab[:5000],
                    scorer=fuzz.ratio,
                    score_cutoff=83.0,
                )

            if match is not None:
                best_word, score, _ = match
                if abs(len(best_word) - len(clean_tok)) <= 2 and best_word != clean_tok:
                    out_tokens.append(best_word)
                    notes.append(f"Исправлена опечатка: «{raw_tok}» → «{best_word}»")
                    continue
            out_tokens.append(raw_tok)

        return " ".join(out_tokens), notes

    def _match_domain_rule(self, q_raw: str, q_norm: str) -> Optional[QueryRule]:
        candidates = [q_norm.lower().strip(), q_raw.lower().strip()]
        tok_sets = [set(_TOKEN_RE.findall(c)) for c in candidates]

        for rule in DOMAIN_QUERY_RULES:
            for trig in rule.triggers:
                t_low = trig.lower()
                if rule.exact_token_only:
                    if " " in t_low:
                        if any(t_low in c for c in candidates):
                            return rule
                    else:
                        if any(t_low in ts for ts in tok_sets):
                            return rule
                else:
                    if any(t_low in c for c in candidates):
                        return rule
        return None

    def process(self, raw_query: str, intent_override: Optional[str] = None) -> ProcessedQuery:
        q0 = (raw_query or "").strip()
        if not q0:
            return ProcessedQuery(
                raw_query="",
                normalized_query="",
                semantic_query="",
                lexical_tokens=[],
                detected_intent="general",
            )

        transformations: List[str] = []
        q_clean, homoglyph_fixes = fix_homoglyphs(q0)
        if homoglyph_fixes:
            transformations.append(f"Устранены символы-двойники: {', '.join(homoglyph_fixes[:2])}")

        q_layout, layout_note = self._maybe_fix_layout(q_clean)
        if layout_note:
            transformations.append(layout_note)

        # First alias pass (catches multi-word Cyrillic transliterations like 'астра линукс')
        q_alias1, alias_notes1 = self._apply_aliases(q_layout)
        transformations.extend(alias_notes1)

        # Fuzzy typo correction pass
        q_typo, typo_notes = self._fix_typos(q_alias1)
        transformations.extend(typo_notes)

        # Second alias pass in case typo fix produced a known alias trigger
        q_norm, alias_notes2 = self._apply_aliases(q_typo)
        transformations.extend(alias_notes2)

        low_norm = q_norm.lower().replace("ё", "е")
        low_orig = q_layout.lower().replace("ё", "е")

        matched_rule = self._match_domain_rule(low_orig, low_norm)

        # Hardware vs Software disambiguation (especially 'сервер')
        has_server_word = any(trig in low_norm or trig in low_orig for trig in SERVER_HARDWARE_TRIGGERS)
        has_sw_qualifier = any(qual in low_norm or qual in low_orig for qual in SERVER_SOFTWARE_QUALIFIERS)

        detected_intent = "general"
        chips: List[DisambiguationChip] = []
        explanation_parts: List[str] = []

        if has_server_word and not has_sw_qualifier:
            active_mode = intent_override if intent_override in ("hardware", "software", "options", "all") else "hardware"
            detected_intent = active_mode
            chips = [
                DisambiguationChip("hardware", "Серверное оборудование (Rack / Tower)", active_mode == "hardware"),
                DisambiguationChip("software", "Серверные ОС и инфраструктурное ПО", active_mode == "software"),
                DisambiguationChip("options", "Комплектующие, шасси и СХД", active_mode == "options"),
                DisambiguationChip("all", "Все категории", active_mode == "all"),
            ]
            if active_mode == "hardware":
                explanation_parts.append(
                    "По запросу «сервер» агент отделил физическое серверное оборудование от серверных лицензий прикладного ПО"
                )
            elif active_mode == "software":
                explanation_parts.append(
                    "Выбрано уточнение: серверные операционные системы, виртуализация и серверное ПО"
                )
            elif active_mode == "options":
                explanation_parts.append(
                    "Выбрано уточнение: серверные шасси, блоки питания, салазки и СХД"
                )
        elif intent_override in ("hardware", "software"):
            detected_intent = intent_override
        elif matched_rule and matched_rule.product_type_hint:
            detected_intent = "hardware" if matched_rule.product_type_hint == "электроника" else "software"

        if matched_rule:
            explanation_parts.append(matched_rule.explanation)
        if transformations and not matched_rule:
            explanation_parts.extend(transformations)

        wants_secondary = bool(_SECONDARY_INTENT_RE.search(low_norm) or _SECONDARY_INTENT_RE.search(low_orig))
        wants_registry = bool(_RU_REGISTRY_RE.search(low_norm) or _RU_REGISTRY_RE.search(low_orig))
        wants_hb = ("дома и бизнеса" in low_norm) or ("дома и бизнеса" in low_orig) or ("home and business" in low_norm)

        ver_match = _VERSION_RE.search(low_norm)
        req_ver = ver_match.group(1) if ver_match else ""

        max_budget: Optional[float] = None
        b_match = _BUDGET_RE.search(low_orig)
        if b_match:
            raw_num = b_match.group(1).replace(" ", "")
            try:
                val = float(raw_num)
                if any(u in b_match.group(0).lower() for u in ("тыс", "к", "k")) and val < 10000:
                    val *= 1000.0
                max_budget = val
                explanation_parts.append(f"Учтен бюджет: до {int(val):,} ₽".replace(",", " "))
            except ValueError:
                pass

        semantic_query = q_norm
        if matched_rule:
            semantic_query = f"{q_norm} — {matched_rule.expanded_query}"
        elif has_server_word and detected_intent == "hardware":
            semantic_query = f"{q_norm} Rack-сервер серверное оборудование платформа стоечный сервер электроника"
        elif has_server_word and detected_intent == "software":
            semantic_query = f"{q_norm} серверная операционная система серверное программное обеспечение"

        raw_lex = _TOKEN_RE.findall(low_norm)
        lexical_tokens: List[str] = []
        for t in raw_lex:
            lexical_tokens.append(t)
            if "-" in t:
                lexical_tokens.extend(p for p in t.split("-") if len(p) >= 2)
        if matched_rule:
            for extra_t in _TOKEN_RE.findall(matched_rule.expanded_query.lower()):
                if extra_t not in lexical_tokens and len(extra_t) >= 3:
                    lexical_tokens.append(extra_t)

        explanation = " · ".join(dict.fromkeys(p for p in explanation_parts if p))
        if not explanation:
            explanation = f"Семантический и лексический поиск по каталогу Store.softline.ru («{q_norm}»)"

        return ProcessedQuery(
            raw_query=q0,
            normalized_query=q_norm,
            semantic_query=semantic_query,
            lexical_tokens=lexical_tokens,
            detected_intent=detected_intent,
            is_server_ambiguous=bool(has_server_word and not has_sw_qualifier),
            transformations=transformations,
            explanation=explanation,
            matched_rule=matched_rule,
            wants_secondary_sku=wants_secondary,
            wants_ru_registry=wants_registry,
            wants_home_business=wants_hb,
            requested_version=req_ver,
            max_budget=max_budget,
            disambiguation_chips=chips,
        )
