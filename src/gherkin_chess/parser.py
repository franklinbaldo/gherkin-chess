from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from gherkin.parser import Parser

from .models import FeatureModel, RuleModel, ScenarioModel, StepModel


class GherkinParseError(ValueError):
    """Raised when Gherkin syntax is invalid or cannot be parsed."""
    pass


def parse_gherkin(text: str) -> FeatureModel:
    """Parse Gherkin text using gherkin-official parser into FeatureModel."""
    try:
        parser = Parser()
        doc = parser.parse(text)
    except Exception as exc:
        raise GherkinParseError(f"Invalid Gherkin syntax: {exc}") from exc

    feature_data = doc.get("feature")
    if not feature_data:
        raise GherkinParseError("No Feature found in Gherkin text.")

    tags = [t["name"].lstrip("@") for t in feature_data.get("tags", [])]

    # Extract origin_fen from tags if present
    origin_fen = None
    cleaned_tags = []
    for t in tags:
        if t.startswith("origin_fen:"):
            raw_fen = t[len("origin_fen:"):]
            origin_fen = raw_fen.replace("_", " ")
        else:
            cleaned_tags.append(t)

    background_steps: List[StepModel] = []
    scenarios: List[ScenarioModel] = []
    rules: List[RuleModel] = []

    for child in feature_data.get("children", []):
        if "background" in child:
            bg = child["background"]
            for s in bg.get("steps", []):
                background_steps.append(_parse_step(s))
        elif "scenario" in child:
            scenarios.append(_parse_scenario(child["scenario"]))
        elif "rule" in child:
            rules.append(_parse_rule(child["rule"]))

    return FeatureModel(
        name=feature_data.get("name", "").strip(),
        description=feature_data.get("description", "").strip(),
        tags=cleaned_tags,
        background_steps=background_steps,
        scenarios=scenarios,
        rules=rules,
        origin_fen=origin_fen,
    )


def _parse_step(step_dict: Dict[str, Any]) -> StepModel:
    kw = step_dict.get("keyword", "").strip()
    text = step_dict.get("text", "").strip()
    kw_type = step_dict.get("keywordType")
    
    data_table = None
    if "dataTable" in step_dict:
        data_table = [
            [cell["value"] for cell in row.get("cells", [])]
            for row in step_dict["dataTable"].get("rows", [])
        ]
        
    doc_string = None
    if "docString" in step_dict:
        doc_string = step_dict["docString"].get("content")

    return StepModel(
        keyword=kw,
        text=text,
        keyword_type=kw_type,
        data_table=data_table,
        doc_string=doc_string,
    )


def _parse_scenario(sc_dict: Dict[str, Any]) -> ScenarioModel:
    tags = [t["name"].lstrip("@") for t in sc_dict.get("tags", [])]
    steps = [_parse_step(s) for s in sc_dict.get("steps", [])]
    examples = sc_dict.get("examples", [])
    return ScenarioModel(
        name=sc_dict.get("name", "").strip(),
        description=sc_dict.get("description", "").strip(),
        tags=tags,
        steps=steps,
        examples=examples,
    )


def _parse_rule(rule_dict: Dict[str, Any]) -> RuleModel:
    tags = [t["name"].lstrip("@") for t in rule_dict.get("tags", [])]
    scenarios = []
    for child in rule_dict.get("children", []):
        if "scenario" in child:
            scenarios.append(_parse_scenario(child["scenario"]))
    return RuleModel(
        name=rule_dict.get("name", "").strip(),
        description=rule_dict.get("description", "").strip(),
        tags=tags,
        scenarios=scenarios,
    )