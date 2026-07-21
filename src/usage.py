from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StageUsage:
    """API activity recorded for one report-generation stage."""

    stage: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    web_search_requests: int = 0


@dataclass(frozen=True, slots=True)
class RunUsage:
    """Combined API activity for a completed report."""

    stages: tuple[StageUsage, ...] = ()

    @property
    def web_search_requests(self) -> int:
        return sum(stage.web_search_requests for stage in self.stages)

    def to_dict(self) -> dict[str, object]:
        return {
            "stages": [
                {
                    "stage": stage.stage,
                    "model": stage.model,
                    "input_tokens": stage.input_tokens,
                    "output_tokens": stage.output_tokens,
                    "cache_creation_input_tokens": (
                        stage.cache_creation_input_tokens
                    ),
                    "cache_read_input_tokens": stage.cache_read_input_tokens,
                    "web_search_requests": stage.web_search_requests,
                }
                for stage in self.stages
            ]
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> RunUsage:
        raw_stages = payload.get("stages", [])
        if not isinstance(raw_stages, list):
            return cls()

        stages: list[StageUsage] = []
        for item in raw_stages:
            if not isinstance(item, dict):
                continue
            try:
                stages.append(StageUsage(**item))
            except TypeError:
                continue
        return cls(tuple(stages))
