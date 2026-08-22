from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_string(s: str | None) -> str:
    if not s:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9]", "", str(s).lower())
    return clean


def extract_domain(url: str | None) -> str:
    if not url:
        return ""
    clean = str(url).lower().replace("https://", "").replace("http://", "").replace("www.", "")
    domain = clean.split("/")[0].split("?")[0]
    return domain


def generate_canonical_entity_id(
    business_name: str | None,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    location: str | None = None,
    google_place_id: str | None = None,
) -> str:
    """Generates a reproducible multi-signal canonical entity identifier hash."""
    if google_place_id and google_place_id.strip():
        raw_key = f"place_id:{google_place_id.strip()}"
    else:
        norm_name = normalize_string(business_name)
        norm_phone = normalize_string(phone)
        norm_email = normalize_string(email)
        norm_domain = extract_domain(website)
        norm_loc = normalize_string(location)

        # Primary composite identity key
        raw_key = f"name:{norm_name}|phone:{norm_phone}|email:{norm_email}|domain:{norm_domain}|loc:{norm_loc}"

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]


class EntityDeduplicator:
    """Multi-signal entity resolution & split protection manager."""

    def __init__(self) -> None:
        self.seen_entities: dict[str, dict[str, Any]] = {}

    def classify_entity_status(self, record: dict[str, Any]) -> str:
        """Classifies identity state as NEW, EXISTING, UPDATED, or DUPLICATE without deleting historical records."""
        entity_id = generate_canonical_entity_id(
            business_name=record.get("Business Name"),
            phone=record.get("Phone"),
            email=record.get("Email"),
            website=record.get("Website"),
            location=record.get("Location"),
        )

        if entity_id not in self.seen_entities:
            self.seen_entities[entity_id] = record
            return "NEW"

        existing = self.seen_entities[entity_id]
        if existing == record:
            return "DUPLICATE"
        else:
            return "UPDATED"


def grouped_stratified_split(
    features: list[dict[str, Any]],
    targets: list[int],
    seed: int = 42,
) -> tuple[
    list[dict[str, Any]],
    list[int],
    list[dict[str, Any]],
    list[int],
    list[dict[str, Any]],
    list[int],
]:
    """Splits dataset into 80% Train, 10% Validation, 10% Test guaranteeing 0 entity leakage AND class stratification."""
    import random

    entity_groups: dict[str, list[tuple[dict[str, Any], int]]] = {}
    for feat, target in zip(features, targets, strict=False):
        eid = generate_canonical_entity_id(
            business_name=feat.get("business_name"),
            location=feat.get("location"),
        )
        if eid not in entity_groups:
            entity_groups[eid] = []
        entity_groups[eid].append((feat, target))

    pos_entities: list[str] = []
    neg_entities: list[str] = []

    for eid, items in entity_groups.items():
        if any(tgt == 1 for _, tgt in items):
            pos_entities.append(eid)
        else:
            neg_entities.append(eid)

    random.seed(seed)
    random.shuffle(pos_entities)
    random.shuffle(neg_entities)

    def split_list(lst: list[str]) -> tuple[set[str], set[str], set[str]]:
        n = len(lst)
        n_tr = int(n * 0.80)
        n_v = int(n * 0.10)
        return set(lst[:n_tr]), set(lst[n_tr : n_tr + n_v]), set(lst[n_tr + n_v :])

    pos_tr, pos_v, pos_te = split_list(pos_entities)
    neg_tr, neg_v, neg_te = split_list(neg_entities)

    train_keys = pos_tr | neg_tr
    val_keys = pos_v | neg_v
    test_keys = pos_te | neg_te

    X_train, y_train = [], []
    X_val, y_val = [], []
    X_test, y_test = [], []

    for eid, items in entity_groups.items():
        for feat, tgt in items:
            if eid in train_keys:
                X_train.append(feat)
                y_train.append(tgt)
            elif eid in val_keys:
                X_val.append(feat)
                y_val.append(tgt)
            elif eid in test_keys:
                X_test.append(feat)
                y_test.append(tgt)

    return X_train, y_train, X_val, y_val, X_test, y_test
