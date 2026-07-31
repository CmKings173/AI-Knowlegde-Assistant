from __future__ import annotations

from app.config import Settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.rag.routing.capability_router import CapabilityRouter
from app.rag.routing.embedding_classifier import (
    EmbeddingRouteClassifier,
    RoutePrototype,
)
from app.rag.routing.models import (
    RequestIntent,
    RouteAffinity,
    RoutingDecision,
    TurnKind,
)
from app.rag.routing.structured_classifier import StructuredRouteClassifier
from app.rag.routing.turn_resolver import TurnResolver


class MultiStageRouter:
    def __init__(
        self,
        turn_resolver: TurnResolver,
        embedding_classifier: EmbeddingRouteClassifier,
        structured_classifier: StructuredRouteClassifier,
        capability_router: CapabilityRouter,
    ) -> None:
        self.turn_resolver = turn_resolver
        self.embedding_classifier = embedding_classifier
        self.structured_classifier = structured_classifier
        self.capability_router = capability_router

    async def route(
        self,
        question: str,
        history: list[dict[str, str]],
        *,
        has_continuation: bool,
    ) -> RoutingDecision:
        turn = self.turn_resolver.resolve(
            question,
            history,
            has_continuation=has_continuation,
        )
        classification = await self.embedding_classifier.classify(
            turn.resolved_query
        )
        qwen_used = (
            not classification.is_confident
            or turn.kind == TurnKind.UNRESOLVED
        )
        if qwen_used:
            classification = await self.structured_classifier.classify(
                question,
                history,
                turn,
            )
        capability = self.capability_router.decide(classification)
        return RoutingDecision(
            turn=turn,
            classification=classification,
            capability=capability,
            qwen_used=qwen_used,
        )


def create_multistage_router(
    settings: Settings,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
) -> MultiStageRouter:
    return MultiStageRouter(
        TurnResolver(),
        EmbeddingRouteClassifier(
            embedding_provider,
            _default_prototypes(settings.route_embedding_min_score),
            minimum_margin=settings.route_embedding_min_margin,
        ),
        StructuredRouteClassifier(llm_provider),
        CapabilityRouter(tools_enabled=False),
    )


def _default_prototypes(threshold: float) -> list[RoutePrototype]:
    return [
        RoutePrototype(
            name="internal_information",
            intent=RequestIntent.ASK_INFORMATION,
            affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
            utterances=(
                "Tra cứu thông tin này trong tài liệu nội bộ công ty.",
                "Công ty quy định vấn đề này như thế nào?",
                "Tôi cần biết thông tin nghiệp vụ theo tài liệu của công ty.",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="internal_instruction",
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
            utterances=(
                "Hướng dẫn tôi thực hiện quy trình nội bộ theo tài liệu công ty.",
                "Các bước của thủ tục nội bộ này là gì?",
                "Tôi cần hướng dẫn xử lý công việc theo SOP nội bộ.",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="internal_section_summary",
            intent=RequestIntent.SUMMARIZE_SECTION,
            affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
            utterances=(
                "Liệt kê đầy đủ các mục trong phần tài liệu nội bộ này.",
                "Tóm tắt toàn bộ nội dung của một phần trong tài liệu công ty.",
                "Phần quy định này gồm những điều nào?",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="conversation_repair",
            intent=RequestIntent.CONVERSATION_REPAIR,
            affinity=RouteAffinity.CONVERSATION,
            utterances=(
                "Tôi không hiểu câu trả lời vừa rồi.",
                "Bạn vừa nói gì vậy?",
                "Hãy giải thích lại câu trả lời trước cho dễ hiểu hơn.",
            ),
            threshold=threshold,
            turn_kind=TurnKind.REPAIR,
        ),
        RoutePrototype(
            name="conversation_continuation",
            intent=RequestIntent.CONTINUE_PREVIOUS,
            affinity=RouteAffinity.CONVERSATION,
            utterances=(
                "Tiếp tục câu trả lời trước.",
                "Nói tiếp phần đang trình bày.",
                "Cho tôi xem phần tiếp theo.",
            ),
            threshold=threshold,
            turn_kind=TurnKind.CONTINUATION,
        ),
        RoutePrototype(
            name="social_conversation",
            intent=RequestIntent.SOCIAL,
            affinity=RouteAffinity.CONVERSATION,
            utterances=(
                "Xin chào, bạn có thể giúp gì?",
                "Cảm ơn bạn.",
                "Tôi đang cảm thấy không thoải mái và muốn nói chuyện một chút.",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="external_information",
            intent=RequestIntent.ASK_INFORMATION,
            affinity=RouteAffinity.EXTERNAL,
            utterances=(
                "Tôi muốn hỏi kiến thức đời sống bên ngoài tài liệu nội bộ.",
                "Cho tôi biết thông tin thời gian thực không có trong tài liệu công ty.",
                "Câu hỏi này không liên quan đến nghiệp vụ và kho kiến thức nội bộ.",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="external_instruction",
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.EXTERNAL,
            utterances=(
                "Hướng dẫn sử dụng một dịch vụ công cộng ngoài tài liệu công ty.",
                "Chỉ tôi làm một việc không thuộc quy trình nội bộ.",
                "Tôi cần hướng dẫn về phần mềm không có trong kho kiến thức nội bộ.",
            ),
            threshold=threshold,
        ),
        RoutePrototype(
            name="tool_action",
            intent=RequestIntent.REQUEST_ACTION,
            affinity=RouteAffinity.TOOL,
            utterances=(
                "Hãy thực hiện hành động này giúp tôi.",
                "Gửi hoặc thay đổi dữ liệu trong một hệ thống giúp tôi.",
                "Dùng công cụ để hoàn thành yêu cầu này.",
            ),
            threshold=threshold,
        ),
    ]
