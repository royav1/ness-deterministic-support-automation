import json
from typing import List, Tuple, Optional, Dict, Any
import uuid

from redis import Redis
from app.schemas.chat_models import Intent, VpnContext


class RedisMemoryStore:
    """
    Redis-backed session store with TTL via Redis key expiration.

    Keys:
      - session:{id}:messages            (Redis LIST)   each item is JSON: {"role": "...", "message": "..."}
      - session:{id}:last_intent         (Redis STRING)
      - session:{id}:vpn_context         (Redis STRING) JSON dump of VpnContext
      - session:{id}:company_id          (Redis STRING)
      - session:{id}:pending_handoff     (Redis STRING) JSON dump of handoff_summary
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 30 * 60) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    def _messages_key(self, session_id: str) -> str:
        return f"session:{session_id}:messages"

    def _intent_key(self, session_id: str) -> str:
        return f"session:{session_id}:last_intent"

    def _vpn_key(self, session_id: str) -> str:
        return f"session:{session_id}:vpn_context"

    def _company_key(self, session_id: str) -> str:
        return f"session:{session_id}:company_id"

    def _pending_handoff_key(self, session_id: str) -> str:
        return f"session:{session_id}:pending_handoff"

    def _touch(self, session_id: str) -> None:
        mk = self._messages_key(session_id)
        ik = self._intent_key(session_id)
        vk = self._vpn_key(session_id)
        ck = self._company_key(session_id)
        pk = self._pending_handoff_key(session_id)

        self.redis.expire(mk, self.ttl_seconds)
        self.redis.expire(ik, self.ttl_seconds)
        self.redis.expire(vk, self.ttl_seconds)
        self.redis.expire(ck, self.ttl_seconds)
        self.redis.expire(pk, self.ttl_seconds)

    def get_or_create_session(self, session_id: str | None) -> tuple[str, bool]:
        new_session_id = session_id or str(uuid.uuid4())
        mk = self._messages_key(new_session_id)

        existed = self.redis.exists(mk) == 1
        return new_session_id, (not existed)

    def session_exists(self, session_id: str) -> bool:
        mk = self._messages_key(session_id)
        return self.redis.exists(mk) == 1

    def add_message(self, session_id: str, role: str, message: str) -> None:
        mk = self._messages_key(session_id)
        item = json.dumps({"role": role, "message": message}, ensure_ascii=False)
        self.redis.rpush(mk, item)
        self._touch(session_id)

    def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        mk = self._messages_key(session_id)
        raw_items = self.redis.lrange(mk, 0, -1)

        history: List[Tuple[str, str]] = []
        for raw in raw_items:
            try:
                obj = json.loads(raw)
                history.append((obj.get("role", ""), obj.get("message", "")))
            except json.JSONDecodeError:
                continue

        self._touch(session_id)
        return history

    def get_last_intent(self, session_id: str) -> Optional[Intent]:
        ik = self._intent_key(session_id)
        val = self.redis.get(ik)
        self._touch(session_id)
        return val  # type: ignore[return-value]

    def set_last_intent(self, session_id: str, intent: Intent) -> None:
        ik = self._intent_key(session_id)
        self.redis.set(ik, intent)
        self._touch(session_id)

    # ===== Company / tenant =====

    def get_company_id(self, session_id: str) -> Optional[str]:
        ck = self._company_key(session_id)
        val = self.redis.get(ck)
        self._touch(session_id)
        return val

    def set_company_id(self, session_id: str, company_id: str) -> None:
        ck = self._company_key(session_id)
        self.redis.set(ck, company_id)
        self._touch(session_id)

    # ===== Pending handoff (tenant missing at escalation time) =====

    def get_pending_handoff_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        pk = self._pending_handoff_key(session_id)
        raw = self.redis.get(pk)
        self._touch(session_id)

        if not raw:
            return None

        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def set_pending_handoff_summary(self, session_id: str, summary: Dict[str, Any]) -> None:
        pk = self._pending_handoff_key(session_id)
        self.redis.set(pk, json.dumps(summary, ensure_ascii=False))
        self._touch(session_id)

    def clear_pending_handoff(self, session_id: str) -> None:
        pk = self._pending_handoff_key(session_id)
        self.redis.delete(pk)
        self._touch(session_id)

    # ===== VPN context storage (Part 2) =====

    def get_vpn_context(self, session_id: str) -> VpnContext:
        vk = self._vpn_key(session_id)
        raw = self.redis.get(vk)

        self._touch(session_id)

        if not raw:
            return VpnContext()

        try:
            return VpnContext.model_validate_json(raw)
        except Exception:
            return VpnContext()

    def set_vpn_context(self, session_id: str, ctx: VpnContext) -> None:
        vk = self._vpn_key(session_id)
        self.redis.set(vk, ctx.model_dump_json())
        self._touch(session_id)

    def clear_vpn_context(self, session_id: str) -> None:
        vk = self._vpn_key(session_id)
        self.redis.delete(vk)
        self._touch(session_id)

    def delete_session(self, session_id: str) -> bool:
        mk = self._messages_key(session_id)
        ik = self._intent_key(session_id)
        vk = self._vpn_key(session_id)
        ck = self._company_key(session_id)
        pk = self._pending_handoff_key(session_id)
        deleted = self.redis.delete(mk, ik, vk, ck, pk)
        return deleted > 0
