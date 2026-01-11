"""
Streaming service for LLM responses.

Implements Server-Sent Events (SSE) for real-time LLM output streaming,
following production best practices for LLM applications.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from sse_starlette.sse import EventSourceResponse
from anthropic import AsyncAnthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessageChunk

from config import get_settings
from core.cache import get_cache

logger = logging.getLogger(__name__)
settings = get_settings()


class StreamEventType(str, Enum):
    """Types of streaming events."""
    START = "start"
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StreamEvent:
    """A streaming event to send to the client."""
    event_type: StreamEventType
    data: Any
    metadata: Optional[dict] = None

    def to_sse(self) -> dict:
        """Convert to SSE format."""
        return {
            "event": self.event_type.value,
            "data": json.dumps({
                "type": self.event_type.value,
                "data": self.data,
                "metadata": self.metadata or {},
            }),
        }


class LLMStreamingService:
    """
    Service for streaming LLM responses using SSE.

    Supports:
    - Token-by-token streaming
    - Tool call notifications
    - Progress updates
    - Error handling
    - Response caching
    """

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.cache = get_cache()

    async def stream_completion(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        use_cache: bool = True,
        cache_key: Optional[str] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream a completion response from Claude.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_cache: Whether to use response caching
            cache_key: Optional custom cache key

        Yields:
            StreamEvent objects for each streaming event
        """
        # Check cache first
        if use_cache and self.cache:
            cached = await self.cache.get_llm_response(
                prompt, self.model,
                system=system, max_tokens=max_tokens, temperature=temperature
            )
            if cached:
                yield StreamEvent(
                    event_type=StreamEventType.START,
                    data={"cached": True},
                )
                yield StreamEvent(
                    event_type=StreamEventType.TOKEN,
                    data=cached.get("content", ""),
                )
                yield StreamEvent(
                    event_type=StreamEventType.COMPLETE,
                    data={"usage": cached.get("usage", {})},
                )
                return

        # Signal start
        yield StreamEvent(
            event_type=StreamEventType.START,
            data={"model": self.model, "cached": False},
        )

        full_response = ""
        usage = {}

        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield StreamEvent(
                        event_type=StreamEventType.TOKEN,
                        data=text,
                    )

                # Get final message for usage stats
                final_message = await stream.get_final_message()
                usage = {
                    "input_tokens": final_message.usage.input_tokens,
                    "output_tokens": final_message.usage.output_tokens,
                }

            # Cache the response
            if use_cache and self.cache:
                await self.cache.set_llm_response(
                    prompt, self.model,
                    {"content": full_response, "usage": usage},
                    system=system, max_tokens=max_tokens, temperature=temperature
                )

            yield StreamEvent(
                event_type=StreamEventType.COMPLETE,
                data={"usage": usage},
            )

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e)},
            )

    async def stream_agent_workflow(
        self,
        workflow_name: str,
        input_data: dict,
        on_step: Optional[callable] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream an agent workflow execution.

        Provides real-time updates as each agent step executes.

        Args:
            workflow_name: Name of the workflow to execute
            input_data: Input data for the workflow
            on_step: Optional callback for each step

        Yields:
            StreamEvent objects for workflow progress
        """
        yield StreamEvent(
            event_type=StreamEventType.START,
            data={"workflow": workflow_name},
        )

        try:
            # Import here to avoid circular imports
            from agents.orchestrator import get_orchestrator

            orchestrator = get_orchestrator()
            workflow_steps = orchestrator.get_workflow_steps(workflow_name)

            for i, step in enumerate(workflow_steps):
                yield StreamEvent(
                    event_type=StreamEventType.THINKING,
                    data={
                        "step": i + 1,
                        "total": len(workflow_steps),
                        "agent": step,
                        "status": "running",
                    },
                )

                # Execute step
                try:
                    result = await orchestrator.execute_step(step, input_data)
                    input_data = result  # Pass to next step

                    yield StreamEvent(
                        event_type=StreamEventType.TOOL_RESULT,
                        data={
                            "step": i + 1,
                            "agent": step,
                            "status": "completed",
                            "result_summary": self._summarize_result(result),
                        },
                    )

                    if on_step:
                        await on_step(step, result)

                except Exception as e:
                    logger.error(f"Step {step} failed: {e}")
                    yield StreamEvent(
                        event_type=StreamEventType.ERROR,
                        data={
                            "step": i + 1,
                            "agent": step,
                            "error": str(e),
                        },
                    )
                    return

            yield StreamEvent(
                event_type=StreamEventType.COMPLETE,
                data={"result": input_data},
            )

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e)},
            )

    def _summarize_result(self, result: Any, max_length: int = 200) -> str:
        """Create a brief summary of a result for streaming updates."""
        if isinstance(result, dict):
            if "items_processed" in result:
                return f"Processed {result['items_processed']} items"
            if "matches_found" in result:
                return f"Found {result['matches_found']} matches"
            if "po_number" in result:
                return f"Created PO #{result['po_number']}"
            return str(result)[:max_length]
        return str(result)[:max_length]


async def create_sse_response(
    event_generator: AsyncGenerator[StreamEvent, None],
) -> EventSourceResponse:
    """
    Create an SSE response from an event generator.

    Args:
        event_generator: Async generator yielding StreamEvent objects

    Returns:
        EventSourceResponse for FastAPI
    """
    async def generate():
        try:
            async for event in event_generator:
                yield event.to_sse()
        except asyncio.CancelledError:
            logger.info("SSE connection cancelled by client")
            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": "Connection cancelled"},
            ).to_sse()

    return EventSourceResponse(generate())


# Singleton instance
_streaming_service: Optional[LLMStreamingService] = None


def get_streaming_service() -> LLMStreamingService:
    """Get or create the streaming service singleton."""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = LLMStreamingService()
    return _streaming_service
