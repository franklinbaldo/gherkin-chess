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
    Preserves origin_fen, tracks records, and loads valid features/scenarios.
    """

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # We store features in a dedicated 'features' subfolder or root_dir
        self.features_dir = self.root_dir / "features"
        self.features_dir.mkdir(parents=True, exist_ok=True)

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
            # Immutability check: if Gherkin specified an origin_fen that contradicts current board
            raise ValueError(
                f"Gherkin specifies origin_fen '{feat.origin_fen}' which conflicts with actual position '{origin_fen}'"
            )
        return self.add_feature(feat, filename=filename)

    def load_all_features(self) -> List[FeatureModel]:
        """Load and parse all Features currently stored in the bundle."""
        features = []
        for file in sorted(self.features_dir.glob("*.md")):
            text = file.read_text(encoding="utf-8")
            # Extract body after frontmatter
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()
                    try:
                        feat = parse_gherkin(body)
                        # Also check frontmatter for origin_fen if not in tags
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