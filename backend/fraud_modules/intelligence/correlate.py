"""Group findings from different modules by the entity they concern.

Each module's score and evidence stay separate. There is no combined score on purpose:
modules measure different things, so an average would not mean anything.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from fraud_modules.intelligence.entities import EntityRef
from fraud_modules.rule_modules import Finding


@dataclass(frozen=True)
class ModuleEvidence:
    module_id: str
    score: Optional[float]
    evidence: Tuple[str, ...]


@dataclass(frozen=True)
class CorrelatedEntity:
    entity: EntityRef
    modules: Tuple[ModuleEvidence, ...]


def _evidence(module_id: str, findings: List[Finding]) -> ModuleEvidence:
    scores = [f.score for f in findings if f.score is not None]
    return ModuleEvidence(module_id, max(scores) if scores else None, tuple(f.explanation for f in findings))


def correlate(findings: Iterable[Finding]) -> Tuple[CorrelatedEntity, ...]:
    grouped: Dict[str, Dict[str, List[Finding]]] = {}
    for f in findings:
        grouped.setdefault(f.account_id, {}).setdefault(f.module_id, []).append(f)
    entities = [
        CorrelatedEntity(
            EntityRef("account", account_id),
            tuple(_evidence(module_id, fs) for module_id, fs in per_module.items()),
        )
        for account_id, per_module in grouped.items()
    ]
    return tuple(sorted(entities, key=lambda e: (-len(e.modules), e.entity.entity_id)))
