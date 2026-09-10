from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class StepModel:
    keyword: str  # Given, When, Then, And, But
    text: str
    keyword_type: Optional[str] = None  # Context, Action, Outcome
    data_table: Optional[List[List[str]]] = None
    doc_string: Optional[str] = None

    def to_gherkin(self) -> str:
        kw = self.keyword.strip()
        lines = [f"    {kw} {self.text}"]
        if self.doc_string:
            lines.append(f'    """\n    {self.doc_string}\n    """')
        if self.data_table:
            for row in self.data_table:
                lines.append("    | " + " | ".join(row) + " |")
        return "\n".join(lines)


@dataclass
class ScenarioModel:
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    steps: List[StepModel] = field(default_factory=list)
    examples: List[dict[str, Any]] = field(default_factory=list)

    def to_gherkin(self) -> str:
        lines = []
        if self.tags:
            tag_str = " ".join(t if t.startswith("@") else f"@{t}" for t in self.tags)
            lines.append(f"  {tag_str}")
        lines.append(f"  Scenario: {self.name}")
        if self.description:
            lines.append(f"    {self.description}")
        for step in self.steps:
            lines.append(step.to_gherkin())
        return "\n".join(lines)


@dataclass
class RuleModel:
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    scenarios: List[ScenarioModel] = field(default_factory=list)

    def to_gherkin(self) -> str:
        lines = []
        if self.tags:
            tag_str = " ".join(t if t.startswith("@") else f"@{t}" for t in self.tags)
            lines.append(f"  {tag_str}")
        lines.append(f"  Rule: {self.name}")
        if self.description:
            lines.append(f"    {self.description}")
        for sc in self.scenarios:
            lines.append(sc.to_gherkin())
        return "\n".join(lines)


@dataclass
class FeatureModel:
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    background_steps: List[StepModel] = field(default_factory=list)
    scenarios: List[ScenarioModel] = field(default_factory=list)
    rules: List[RuleModel] = field(default_factory=list)
    origin_fen: Optional[str] = None

    def to_gherkin(self) -> str:
        lines = []
        tags_all = list(self.tags)
        if self.origin_fen:
            # We can encode origin_fen in tags or keep as comment/header
            fen_tag = f"@origin_fen:{self.origin_fen.replace(' ', '_')}"
            if not any(t.startswith("@origin_fen:") for t in tags_all):
                tags_all.append(fen_tag)

        if tags_all:
            tag_str = " ".join(t if t.startswith("@") else f"@{t}" for t in tags_all)
            lines.append(tag_str)

        lines.append(f"Feature: {self.name}")
        if self.description:
            lines.append(f"  {self.description}")
        if self.background_steps:
            lines.append("  Background:")
            for step in self.background_steps:
                lines.append(step.to_gherkin())
        for rule in self.rules:
            lines.append(rule.to_gherkin())
        for sc in self.scenarios:
            lines.append(sc.to_gherkin())
        return "\n".join(lines)