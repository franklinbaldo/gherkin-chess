from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import okf_parser

from .models import FeatureModel, ScenarioModel, StepModel, RuleModel


def _escape_yaml_str(val: str) -> str:
    """Safely format string for YAML value."""
    val = val.replace('"', '\\"')
    return f'"{val}"'


def feature_to_okf_markdown(feature: FeatureModel) -> str:
    """
    Render FeatureModel as an OKF markdown document with YAML frontmatter.
    Frontmatter holds structural metadata (type: Feature, title, tags, origin_fen)
    and body holds the readable Gherkin representation.
    """
    frontmatter: Dict[str, Any] = {
        "type": "Feature",
        "title": feature.name,
    }
    if feature.tags:
        frontmatter["tags"] = feature.tags
    if feature.origin_fen:
        frontmatter["origin_fen"] = feature.origin_fen
    if feature.description:
        frontmatter["description"] = feature.description

    fm_lines = ["---"]
    fm_lines.append(f"type: {frontmatter['type']}")
    fm_lines.append(f"title: {_escape_yaml_str(frontmatter['title'])}")
    if "origin_fen" in frontmatter:
        fm_lines.append(f"origin_fen: {_escape_yaml_str(frontmatter['origin_fen'])}")
    if "description" in frontmatter:
        fm_lines.append(f"description: {_escape_yaml_str(frontmatter['description'])}")
    if "tags" in frontmatter and frontmatter["tags"]:
        tags_json = json.dumps(frontmatter["tags"])
        fm_lines.append(f"tags: {tags_json}")
    fm_lines.append("---")

    body = feature.to_gherkin()
    return "\n".join(fm_lines) + "\n\n" + body + "\n"


def scenario_to_okf_markdown(scenario: ScenarioModel, origin_fen: Optional[str] = None) -> str:
    """
    Render ScenarioModel as an OKF markdown document with YAML frontmatter.
    Type is 'Scenario'.
    """
    fm_lines = ["---"]
    fm_lines.append("type: Scenario")
    fm_lines.append(f"title: {_escape_yaml_str(scenario.name)}")
    if origin_fen:
        fm_lines.append(f"origin_fen: {_escape_yaml_str(origin_fen)}")
    if scenario.description:
        fm_lines.append(f"description: {_escape_yaml_str(scenario.description)}")
    if scenario.tags:
        tags_json = json.dumps(scenario.tags)
        fm_lines.append(f"tags: {tags_json}")
    fm_lines.append("---")

    body = scenario.to_gherkin()
    return "\n".join(fm_lines) + "\n\n" + body + "\n"


def materialize_feature(feature: FeatureModel, target_dir: Path, filename: Optional[str] = None) -> Path:
    """
    Materialize a FeatureModel into target_dir as an OKF document.
    Validates by loading the bundle via okf_parser.load_bundle.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    if not filename:
        slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in feature.name.lower())
        filename = f"{slug or 'feature'}.md"

    target_file = target_dir / filename
    content = feature_to_okf_markdown(feature)
    target_file.write_text(content, encoding="utf-8")

    # Validate with real okf_parser
    try:
        bundle = okf_parser.load_bundle(target_dir)
        # Check that bundle parses
        count = bundle.concepts.count().execute()
        if count == 0:
            target_file.unlink(missing_ok=True)
            raise ValueError(f"OKF bundle loaded 0 concepts from {target_dir}")
    except Exception as exc:
        target_file.unlink(missing_ok=True)
        raise ValueError(f"Failed to materialize via okf_parser: {exc}") from exc

    return target_file