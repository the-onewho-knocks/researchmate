"""backend/app/services/llm/policy.py"""
"""Which provider does which work.

The goal is not a fixed ratio of criteria but a hard cap on Gemini requests and
tokens, because the free tier locks up after a handful of calls. Gemini gets the
high-impact components and the second opinion on anything the local model is
unsure about; the local model does the bulk.

    P0  title + abstract + introduction        -> Gemini
    P1  tier B elsewhere                       -> Gemini while the token budget lasts
    P2  tier C elsewhere                       -> local
    P3  unresolved / needs_review from local   -> Gemini, if quota remains
"""
import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import LLMError, RateLimitError
from app.schemas.report import Usage
from app.schemas.verdict import Verdict
from app.services.framework.compiler import compile_component
from app.services.llm.token_budget import estimate_tokens

from .base import LLMClient
from .coach import write_feedback
from .judge import GroupInput, judge_group
from .rate_limit import GeminiQuota
from .suggest import suggest_fixes

log = logging.getLogger(__name__)

# Components whose verdicts shape a reader's first impression.
IMPORTANT_COMPONENTS = frozenset({"title", "abstract", "introduction"})


@dataclass
class RoutingDecision:
    gemini: list[GroupInput]
    local: list[GroupInput]


def priority(item: GroupInput) -> int:
    if item.component.key in IMPORTANT_COMPONENTS:
        return 0
    if any(p.criterion.tier == "B" for p in item.pendings):
        return 1
    return 2


def _block_tokens(item: GroupInput) -> int:
    only = {p.criterion.id for p in item.pendings}
    return estimate_tokens(compile_component(item.component, only) + "\nTEXT:\n" + item.text)


class LLMPolicy:
    """Routes judge, suggestion and coach work across Gemini and a local model."""

    name = "policy"

    def __init__(
        self,
        gemini: LLMClient | None,
        local: LLMClient | None,
        quota: GeminiQuota,
        settings: Settings,
    ):
        self.gemini = gemini
        self.local = local
        self.quota = quota
        self.settings = settings

    # ---- state -------------------------------------------------------

    @property
    def gemini_available(self) -> bool:
        return bool(self.gemini and self.gemini.available and not self.quota.cooling_down())

    @property
    def local_available(self) -> bool:
        return bool(self.local and self.local.available)

    @property
    def available(self) -> bool:
        return self.gemini_available or self.local_available

    @property
    def model(self) -> str:
        names = []
        if self.gemini_available:
            names.append(self.gemini.model)
        if self.local_available:
            names.append(self.local.model)
        return " + ".join(names)

    def cache_key(self) -> str:
        """Everything that changes the verdicts, for the result cache."""
        return "|".join(
            [
                self.gemini.model if self.gemini_available else "no-gemini",
                self.local.model if self.local_available else "no-local",
                f"r{self.settings.routing_version}",
            ]
        )

    # ---- quota accounting -------------------------------------------

    @staticmethod
    def _gemini_used(usage: Usage) -> tuple[int, int]:
        slot = usage.by_provider.get("gemini")
        return (slot.input_tokens, slot.output_tokens) if slot else (0, 0)

    @staticmethod
    def _gemini_calls(usage: Usage) -> int:
        slot = usage.by_provider.get("gemini")
        return slot.calls if slot else 0

    def _calls_left(self, usage: Usage) -> int:
        return max(0, self.settings.gemini_max_calls_per_eval - self._gemini_calls(usage))

    def _tracked_gemini(self, usage: Usage, fn):
        """Run a Gemini call and record its tokens against the local quota guard."""
        before_in, before_out = self._gemini_used(usage)
        try:
            return fn()
        except RateLimitError:
            self.quota.trip(self.settings.gemini_circuit_breaker_s)
            raise
        finally:
            after_in, after_out = self._gemini_used(usage)
            if after_in > before_in or after_out > before_out:
                self.quota.record(after_in - before_in, after_out - before_out)

    # ---- judge -------------------------------------------------------

    def _split(
        self, items: list[GroupInput], system: str, template: str, settings: Settings
    ) -> RoutingDecision:
        if not self.gemini_available or not self.quota.can_call():
            return RoutingDecision([], list(items))

        overhead = estimate_tokens(system) + estimate_tokens(template)
        total_items = sum(_block_tokens(it) for it in items)
        ordered = sorted(items, key=lambda it: (priority(it), -_block_tokens(it)))

        # The heuristic decides the order; the token share is the hard cut, so a paper
        # with many tier-B groups cannot quietly push Gemini past its target.
        p0 = [it for it in ordered if priority(it) == 0]
        p0_cost = sum(_block_tokens(it) for it in p0)
        budget = max(int(total_items * settings.gemini_token_share), p0_cost)
        if not p0:
            # Small workload with no headline component: let the first tier-B group through
            # instead of starving the intelligent model entirely.
            first_p1 = next((it for it in ordered if priority(it) == 1), None)
            if first_p1 is not None:
                budget = max(budget, _block_tokens(first_p1))
        budget = min(budget, settings.gemini_max_input_tokens - overhead)

        gemini: list[GroupInput] = []
        local: list[GroupInput] = []
        for it in ordered:
            cost = _block_tokens(it)
            if priority(it) == 0 and budget - cost >= 0:
                gemini.append(it)
                budget -= cost
            elif priority(it) == 1 and budget - cost >= 0 and self.quota.can_call(cost):
                gemini.append(it)
                budget -= cost
            else:
                local.append(it)
        return RoutingDecision(gemini, local)

    def _chunks(
        self, items: list[GroupInput], settings: Settings
    ) -> list[list[GroupInput]]:
        chunks: list[list[GroupInput]] = []
        current: list[GroupInput] = []
        tokens = 0
        for it in items:
            cost = _block_tokens(it)
            full = (
                len(current) >= settings.local_max_groups_per_call
                or tokens + cost > settings.local_max_tokens_per_call
            )
            if current and full:
                chunks.append(current)
                current, tokens = [], 0
            current.append(it)
            tokens += cost
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _escalation_items(
        local_items: list[GroupInput], out: dict[str, Verdict], limit: int
    ) -> list[GroupInput]:
        """Criteria the local model could not answer, or left for a human."""
        result: list[GroupInput] = []
        budget = limit
        for it in local_items:
            picked = []
            for p in it.pendings:
                if budget <= 0:
                    break
                verdict = out.get(p.criterion.id)
                if verdict is None or verdict.status == "needs_review":
                    picked.append(p)
                    budget -= 1
            if picked:
                result.append(GroupInput(it.component, picked, it.text))
        return result

    @staticmethod
    def _missing_subset(
        items: list[GroupInput], out: dict[str, Verdict]
    ) -> list[GroupInput]:
        """Groups whose criteria the provider did not answer (bad JSON, empty reply)."""
        result: list[GroupInput] = []
        for it in items:
            picked = [p for p in it.pendings if p.criterion.id not in out]
            if picked:
                result.append(GroupInput(it.component, picked, it.text))
        return result

    def judge(
        self,
        items: list[GroupInput],
        system: str,
        local_system: str,
        template: str,
        usage: Usage,
        settings: Settings,
    ) -> dict[str, Verdict]:
        if not items:
            return {}

        decision = self._split(items, system, template, settings)
        out: dict[str, Verdict] = {}
        gemini_failed = False

        if decision.gemini:
            try:
                out.update(
                    self._tracked_gemini(
                        usage,
                        lambda: judge_group(
                            self.gemini, system, template, decision.gemini, usage, settings
                        ),
                    )
                )
            except (RateLimitError, LLMError) as exc:
                log.warning("Gemini judge unavailable, falling back to local: %s", exc)
                gemini_failed = True
                decision.local = decision.gemini + decision.local
            else:
                # A call can "succeed" and still answer only some criteria.
                missing = self._missing_subset(decision.gemini, out)
                if missing:
                    log.warning(
                        "Gemini answered %d of %d groups; rerouting the rest locally.",
                        len(decision.gemini) - len(missing), len(decision.gemini),
                    )
                    decision.local = missing + decision.local

        if decision.local:
            if not self.local_available:
                log.warning("Local LLM unavailable; %d groups left for the fallback", len(decision.local))
            else:
                for chunk in self._chunks(decision.local, settings):
                    try:
                        out.update(
                            judge_group(self.local, local_system, template, chunk, usage, settings)
                        )
                    except RateLimitError:
                        log.warning("Local LLM refused a call; stopping local judging.")
                        break

        # Second opinion: only for work the local model could not settle.
        if (
            not gemini_failed
            and decision.local
            and self.gemini_available
            and self._calls_left(usage) > 0
        ):
            retry = self._escalation_items(
                decision.local, out, settings.gemini_escalation_max
            )
            if retry and self.quota.can_call(sum(_block_tokens(it) for it in retry)):
                try:
                    out.update(
                        self._tracked_gemini(
                            usage,
                            lambda: judge_group(
                                self.gemini, system, template, retry, usage, settings
                            ),
                        )
                    )
                except (RateLimitError, LLMError) as exc:
                    log.warning("Escalation skipped: %s", exc)

        return out

    # ---- suggestions and coach ---------------------------------------

    def _premium_order(self, usage: Usage) -> list[LLMClient]:
        """Prefer the intelligent model, but never leave the user without an answer."""
        clients: list[LLMClient] = []
        if (
            self.gemini_available
            and self.quota.can_call()
            and self._calls_left(usage) > 0
        ):
            clients.append(self.gemini)
        if self.local_available:
            clients.append(self.local)
        return clients

    def suggest(self, template: str, items, usage: Usage):
        if not items:
            return {}
        for client in self._premium_order(usage):
            try:
                if getattr(client, "name", "") == "gemini":
                    result = self._tracked_gemini(
                        usage, lambda c=client: suggest_fixes(c, template, items, usage)
                    )
                else:
                    result = suggest_fixes(client, template, items, usage)
            except (RateLimitError, LLMError):
                continue
            if result:
                return result
        return {}

    def coach(self, template: str, verdicts: list[Verdict], usage: Usage) -> str | None:
        for client in self._premium_order(usage):
            try:
                if getattr(client, "name", "") == "gemini":
                    text = self._tracked_gemini(
                        usage, lambda c=client: write_feedback(c, template, verdicts, usage)
                    )
                else:
                    text = write_feedback(client, template, verdicts, usage)
            except (RateLimitError, LLMError):
                continue
            if text:
                return text
        return None
