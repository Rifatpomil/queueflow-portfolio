"""AI-powered features – service suggestion, wait prediction, insights."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.ticket_repo import TicketRepository

logger = get_logger(__name__)


class AIService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ticket_repo = TicketRepository(session)
        self.analytics_repo = AnalyticsRepository(session)
        self.settings = get_settings()

    async def suggest_service(
        self, tenant_id: UUID, location_id: UUID, query: str
    ) -> dict:
        """
        Suggest the best service from natural language.
        Uses AI when configured, else heuristic keyword matching.
        """
        services = await self._get_services(tenant_id, location_id)
        if not services:
            return {"suggested_service_id": None, "suggested_service_name": None, "confidence": 0}

        # Try real AI first
        if self.settings.ai_api_key and self.settings.ai_provider != "mock":
            result = await self._ai_suggest_service(query, services)
            if result:
                return result

        # Fallback: heuristic keyword matching
        return await self._heuristic_suggest_service(query, services)

    async def _ai_suggest_service(
        self, query: str, services: list[dict]
    ) -> dict | None:
        """Call Groq/OpenAI to suggest service."""
        import httpx

        service_names = [s["name"] for s in services]
        prompt = f"""You are a queue management assistant. Given this customer request, pick the most relevant service.

Customer request: "{query}"
Available services: {service_names}

Reply with ONLY the exact service name from the list, nothing else. If unclear, reply with the first service."""

        try:
            if self.settings.ai_provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.settings.ai_api_key}"}
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 0.2,
                }
            else:
                base = self.settings.ai_base_url or "https://api.openai.com"
                url = f"{base.rstrip('/')}/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.settings.ai_api_key}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 0.2,
                }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

            for s in services:
                if s["name"].lower() in content.lower():
                    return {
                        "suggested_service_id": str(s["id"]),
                        "suggested_service_name": s["name"],
                        "confidence": 0.9,
                    }
        except Exception as exc:
            logger.warning("ai_suggest_failed", error=str(exc))
        return None

    async def _heuristic_suggest_service(
        self, query: str, services: list[dict]
    ) -> dict:
        """Keyword-based service suggestion when AI unavailable."""
        q = query.lower()
        keywords: dict[str, list[str]] = {}
        for s in services:
            name = s["name"].lower()
            keywords[name] = [
                name,
                *re.findall(r"\w+", name),
                (s.get("category") or "").lower(),
            ]

        best = None
        best_score = 0
        for s in services:
            score = sum(
                2 if kw in q else (1 if kw in q else 0)
                for kw in keywords.get(s["name"].lower(), [])
                if kw
            )
            if score > best_score:
                best_score = score
                best = s

        if best:
            return {
                "suggested_service_id": str(best["id"]),
                "suggested_service_name": best["name"],
                "confidence": min(0.85, 0.5 + best_score * 0.1),
            }
        return {
            "suggested_service_id": str(services[0]["id"]),
            "suggested_service_name": services[0]["name"],
            "confidence": 0.3,
        }

    async def _get_services(
        self, tenant_id: UUID, location_id: UUID
    ) -> list[dict]:
        """Fetch services for tenant/location."""
        from sqlalchemy import or_, select
        from app.models.service import Service

        result = await self.session.execute(
            select(Service).where(
                Service.tenant_id == tenant_id,
                Service.active == True,
                or_(
                    Service.location_id.is_(None),
                    Service.location_id == location_id,
                ),
            )
        )
        rows = result.scalars().all()
        return [{"id": r.id, "name": r.name, "category": r.category} for r in rows]

    async def predict_wait_time(self, location_id: UUID) -> dict:
        """
        Predict wait time in minutes based on queue depth and historical throughput.
        """
        data = await self.ticket_repo.signage_snapshot(location_id)
        waiting = data["waiting_count"]
        avg_wait = data["avg_wait_seconds"]

        # Simple model: wait = queue_depth * avg_service_time_per_ticket
        # Use historical avg_wait as proxy for per-ticket service time when available
        if avg_wait and avg_wait > 0:
            # avg_wait is from created→called; approximate service time as 1/3 of that
            est_per_ticket_min = (avg_wait / 60) * 0.4 + 2  # baseline ~2 min
        else:
            est_per_ticket_min = 5.0  # default 5 min per ticket

        predicted_min = max(0, waiting * est_per_ticket_min)
        return {
            "predicted_wait_minutes": round(predicted_min, 1),
            "waiting_count": waiting,
            "confidence": 0.7 if avg_wait else 0.5,
        }

    async def get_insights(
        self, location_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> dict:
        """
        AI or heuristic insights from KPI data.
        """
        kpi = await self.analytics_repo.kpi_summary(location_id, from_dt, to_dt)

        # Build insight bullets
        insights: list[str] = []
        total = kpi.get("total_tickets") or 0
        completed = kpi.get("completed_tickets") or 0
        throughput = kpi.get("throughput_per_hour") or 0
        avg_wait = kpi.get("avg_wait_seconds")
        p95_wait = kpi.get("p95_wait_seconds")

        if total > 0:
            completion_rate = (completed / total) * 100
            insights.append(f"Completion rate: {completion_rate:.0f}% ({completed}/{total} tickets)")
        if throughput > 0:
            insights.append(f"Throughput: ~{throughput:.0f} customers/hour")
        if avg_wait:
            insights.append(f"Average wait: {avg_wait / 60:.1f} minutes")
        if p95_wait:
            insights.append(f"95th percentile wait: {p95_wait / 60:.1f} minutes")
        if throughput > 10 and avg_wait and avg_wait > 600:
            insights.append("Consider adding a counter during peak hours")
        if not insights:
            insights.append("Not enough data for insights yet")

        return {
            "insights": insights,
            "kpi": kpi,
            "summary": " | ".join(insights[:3]),
        }
