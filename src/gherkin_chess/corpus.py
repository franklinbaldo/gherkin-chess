from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import okf_parser

from .models import FeatureModel, ScenarioModel, StepModel
from .parser import parse_gherkin
from .materializer import materialize_feature


class CorpusManager:
    """
    Manages reading from and writing to the persistent OKF knowledge bundle.
    Preserves origin_fen, tracks application history, and supports reuse/divergence.
    """

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir = self.root_dir / "features"
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.root_dir / "application_history.jsonl"

    def record_application(
        self,
        scenario_name: str,
        origin_fen: str,
        application_fen: str,
        move: str,
        game_id: str,
        epistemic_mode: str,  # 'new' | 'reuse' | 'divergence'
        diverged_from: Optional[str] = None,
        divergence_reason: Optional[str] = None,
    ):
        """Record an application event for historical consistency tracking."""
        record = {
            "scenario_name": scenario_name,
            "origin_fen": origin_fen,
            "application_fen": application_fen,
            "move": move,
            "game_id": game_id,
            "epistemic_mode": epistemic_mode,
            "diverged_from": diverged_from,
            "divergence_reason": divergence_reason,
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_scenario_applications(self, scenario_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve historical applications of scenarios."""
        if not self.history_file.exists():
            return []
        events = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ev = json.loads(line)
                    if scenario_name is None or ev.get("scenario_name") == scenario_name:
                        events.append(ev)
        return events

    def get_application_metrics(self) -> Dict[str, Any]:
        """Compute metrics regarding reuse, new knowledge, and divergence."""
        events = self.get_scenario_applications()
        new_count = sum(1 for e in events if e.get("epistemic_mode") == "new")
        reuse_count = sum(1 for e in events if e.get("epistemic_mode") == "reuse")
        div_count = sum(1 for e in events if e.get("epistemic_mode") == "divergence")
        
        scenario_counts: Dict[str, int] = {}
        for e in events:
            name = e.get("scenario_name", "")
            if name:
                scenario_counts[name] = scenario_counts.get(name, 0) + 1

        return {
            "total_applications": len(events),
            "new_knowledge_count": new_count,
            "reused_count": reuse_count,
            "divergence_count": div_count,
            "scenario_usage": scenario_counts,
        }

    def add_feature(self, feature: FeatureModel, filename: Optional[str] = None) -> Path:
        """Persist and materialize a FeatureModel into the OKF bundle."""
        if not feature.origin_fen:
            raise ValueError("FeatureModel must have origin_fen before materialization in corpus.")
        return materialize_feature(feature, self.features_dir, filename=filename)

    def add_gherkin(self, gherkin_text: str, origin_fen: str, filename: Optional[str] = None) -> Path:
        """Parse Gherkin text, ensure origin_fen is attached, and materialize."""
        feat = parse_gherkin(gherkin_text)
        if not feat.origin_fen:
            feat.origin_fen = origin_fen
        elif feat.origin_fen != origin_fen:
            raise ValueError(
                f"Gherkin specifies origin_fen '{feat.origin_fen}' which conflicts with actual position '{origin_fen}'"
            )
        return self.add_feature(feat, filename=filename)

    def find_scenario(self, scenario_name: str) -> Optional[tuple[ScenarioModel, FeatureModel]]:
        """Look up a scenario by exact or case-insensitive name."""
        sc_lower = scenario_name.strip().lower()
        for feat in self.load_all_features():
            for sc in feat.scenarios:
                if sc.name.strip().lower() == sc_lower:
                    return sc, feat
        return None

    def load_all_features(self) -> List[FeatureModel]:
        """Load and parse all Features currently stored in the bundle."""
        features = []
        for file in sorted(self.features_dir.glob("*.md")):
            text = file.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()
                    try:
                        feat = parse_gherkin(body)
                        fm_str = parts[1]
                        for line in fm_str.splitlines():
                            if line.startswith("origin_fen:"):
                                raw_fen = line.split(":", 1)[1].strip().strip('"').strip("'")
                                if not feat.origin_fen:
                                    feat.origin_fen = raw_fen
                        features.append(feat)
                    except Exception:
                        pass
        return features

    def get_bundle(self) -> Any:
        """Load native OKF Bundle using okf_parser."""
        return okf_parser.load_bundle(self.features_dir)