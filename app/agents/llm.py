import time

from smolagents import OpenAIServerModel

from ..config import settings


class RobustServerModel(OpenAIServerModel):
    def __init__(
        self,
        model_id: str,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        fallback_model_ids: list[str] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.5,
    ):
        super().__init__(model_id=model_id, api_base=api_base, api_key=api_key)
        self._chain = [model_id] + list(fallback_model_ids or [])
        self._max_retries = max_retries
        self._base_delay = base_delay

    def generate(self, messages, **kwargs):
        last_error: Exception | None = None
        for pos, model_id in enumerate(self._chain):
            self.model_id = model_id
            for attempt in range(1, self._max_retries + 1):
                try:
                    return super().generate(messages, **kwargs)
                except Exception as exc:
                    last_error = exc
                    time.sleep(self._base_delay * attempt)
            if pos < len(self._chain) - 1:
                print(f"[fallback] {model_id} agotado -> {self._chain[pos + 1]}")
        if last_error is not None:
            raise last_error


def build_model() -> RobustServerModel:
    return RobustServerModel(
        model_id=settings.model_name,
        api_base=settings.model_base_url,
        api_key=settings.model_api_key,
        fallback_model_ids=settings.model_fallback,
    )