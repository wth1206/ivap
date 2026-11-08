"""Generate the eight-section detection analysis report.

Numbers are computed by :mod:`app.services.stats`; the LLM only writes prose
from those facts.  Mock mode is deterministic, clearly labelled and never
presented as a real LLM result.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.detection import DetectionResult, DetectionTask
from app.models.report import LLMReport
from app.schemas.analysis import AnalysisReportResponse, AnalysisSections, AnalysisUsage
from app.services.detection_service import get_task
from app.services.llm_service import LLMJsonResult, LLMOutputError, LLMService
from app.services.stats import BoxRecord, compute_facts, sample_boxes
from app.utils.time import to_iso

logger = logging.getLogger(__name__)

PROMPT_VERSION = "analysis-v1"

SECTION_TITLES = (
    ("basic_info", "检测任务基本信息"),
    ("overall_count", "目标总体数量"),
    ("class_distribution", "各类别目标分布"),
    ("density_analysis", "目标密集程度分析"),
    ("spatial_distribution", "目标空间分布描述"),
    ("characteristics", "检测结果特点"),
    ("limitations", "可能存在的检测局限"),
    ("conclusion", "总结"),
)

SYSTEM_PROMPT = """你是无人机遥感图像目标检测分析助手。
必须遵守：
1. 只能使用用户提供的 facts 中的数字、类别和空间统计；不得修改、补全或编造任何数量。
2. 不得编造 mAP、precision、recall、训练集规模、硬件性能或实验结论；facts 未提供的信息必须写“未提供，无法判断”。
3. 密度等级、网格占比、最近邻距离、边缘比例、尺寸分布都是基于检测框的启发式统计，不等于真实场景真值。
4. 用中文、专业、简洁地写分析；不要输出 Markdown 代码块，只输出 JSON 对象。
5. JSON 必须且只能包含以下 8 个键：basic_info, overall_count, class_distribution, density_analysis, spatial_distribution, characteristics, limitations, conclusion。
6. 每个字段的值必须是**字符串**（中文句子），不能是对象、数组或数字；例如 overall_count 写“共检测到 33 个目标”，不能写 33。
7. facts 中的阈值、定义、计数是最终值，严禁修改。characteristics 必须直接使用 facts.confidence.low_confidence_threshold（0.4）和 high_confidence_threshold（0.7）及其对应计数，不得改成 0.5 或其他阈值。"""

USER_PROMPT_TEMPLATE = """下面是同一次检测任务的真实统计 facts（由 Python 计算）：
```json
{facts_json}
```

请基于这些 facts 输出 JSON，8 个字段的要求：
- basic_info：任务 ID、图像名、图像尺寸、模型名、检测参数。
- overall_count：目标总数（必须与 facts 一致）。
- class_distribution：各类别数量与占比（必须与 facts 一致）。
- density_analysis：每百万像素目标数、密度等级及阈值说明。
- spatial_distribution：3×3 网格分布、主要区域、最近邻距离、边缘目标比例。
- characteristics：置信度均值/范围、低置信度（阈值必须用 facts 的 0.4）与高置信度（阈值必须用 facts 的 0.7）数量、尺寸分布、重叠情况；不得改写阈值。
- limitations：说明未提供 mAP/ground truth、密度阈值是启发式、小目标/遮挡等只能基于现有统计谨慎表述。
- conclusion：2-4 句总结，不引入 facts 之外的数据。

只输出合法 JSON，不要输出任何解释文字。每个字段的值必须是字符串，不能嵌套对象或数组。"""


def _build_facts(task: DetectionTask, results: List[DetectionResult]) -> Dict[str, Any]:
    boxes = [
        BoxRecord(
            class_name=item.class_name,
            confidence=float(item.confidence),
            bbox=(item.x1, item.y1, item.x2, item.y2),
        )
        for item in results
    ]
    stats = compute_facts(task.image_width, task.image_height, boxes)
    return {
        "task": {
            "task_id": task.id,
            "image_name": task.image_name,
            "model_name": task.model_name,
            "image_width": task.image_width,
            "image_height": task.image_height,
            "conf_threshold": task.conf_threshold,
            "iou_threshold": task.iou_threshold,
            "created_at": to_iso(task.created_at),
        },
        "statistics": stats,
        "sample_detections": sample_boxes(boxes, limit=30),
        "notes": [
            "所有数量与空间指标由 Python 从检测框计算。",
            "未提供 ground truth、mAP、precision、recall，不能推断模型真实精度。",
            "密度等级阈值：稀疏<5，中等5-20，密集20-50，极密集>50（目标/百万像素）。",
        ],
    }


def _build_messages(facts: Dict[str, Any]) -> List[Dict[str, str]]:
    facts_json = json.dumps(facts, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(facts_json=facts_json)},
    ]


def _validate_sections(data: Dict[str, Any], raw_content: str = "") -> AnalysisSections:
    def coerce(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    coerced = {
        field: coerce(data.get(field))
        for field, _title in SECTION_TITLES
    }
    try:
        return AnalysisSections.model_validate(coerced)
    except ValidationError as exc:
        raise LLMOutputError(
            "LLM 输出缺少必需的 8 个字段或字段为空",
            raw_content=raw_content,
            details={"errors": exc.errors()[:5]},
        ) from exc


async def _generate_with_llm(
    settings: Settings,
    facts: Dict[str, Any],
) -> Tuple[AnalysisSections, LLMJsonResult]:
    service = LLMService(settings)
    messages = _build_messages(facts)
    try:
        try:
            result = await service.chat_json(messages, max_tokens=settings.llm_max_tokens)
            sections = _validate_sections(result.data, result.raw_content)
            return sections, result
        except LLMOutputError as first_error:
            repair = messages + [
                {
                    "role": "assistant",
                    "content": (first_error.raw_content or "(空响应)")[:6000],
                },
                {
                    "role": "user",
                    "content": (
                        f"上一次输出不符合要求：{first_error.message}。"
                        "请严格输出包含 8 个键的 JSON 对象，不要 Markdown，不要解释。"
                    ),
                },
            ]
            logger.warning("Retrying LLM output after invalid response: %s", first_error.message)
            result = await service.chat_json(repair, max_tokens=settings.llm_max_tokens)
            sections = _validate_sections(result.data, result.raw_content)
            return sections, result
    finally:
        await service.aclose()


def _mock_sections(facts: Dict[str, Any]) -> AnalysisSections:
    task = facts["task"]
    stats = facts["statistics"]
    classes = stats["class_statistics"]
    grid = stats["grid_3x3"]
    density = stats["density"]
    nearest = stats["nearest_neighbor"]
    edge = stats["edge"]
    size = stats["size_distribution"]
    confidence = stats["confidence"]

    class_text = "、".join(f"{name} {count} 个" for name, count in classes.items()) or "未检测到目标"
    total = stats["total_objects"]
    percentages = "、".join(
        f"{name} {round(count / total * 100, 1)}%"
        for name, count in classes.items()
    ) if total else "无"

    return AnalysisSections(
        basic_info=(
            f"检测任务 {task['task_id']}，图像 {task['image_name']}"
            f"（{task['image_width']}×{task['image_height']}），模型 {task['model_name']}，"
            f"conf={task['conf_threshold']}，iou={task['iou_threshold']}。"
        ),
        overall_count=f"共检测到 {total} 个目标。" if total else "本次任务未检测到目标。",
        class_distribution=f"类别数量：{class_text}；占比：{percentages}。",
        density_analysis=(
            f"目标密度约 {density['per_megapixel']} 个/百万像素，"
            f"按本项目启发式阈值属于“{density['level']}”。"
            f"阈值说明：{density['thresholds']}。"
        ),
        spatial_distribution=(
            f"3×3 网格中目标最多的区域是{grid['dominant']}；"
            f"各区域数量：{json.dumps(grid['cells'], ensure_ascii=False)}。"
            f"最近邻平均距离 {nearest['mean_px']} px"
            f"（约对角线的 {nearest['mean_percent_of_diagonal']}%）；"
            f"靠近边缘的目标 {edge['count']} 个，占 {round(edge['ratio'] * 100, 1)}%。"
        ),
        characteristics=(
            f"置信度均值 {confidence['mean']}，范围 {confidence['min']}–{confidence['max']}；"
            f"低置信目标（<0.4）{confidence['low_confidence_count']} 个。"
            f"尺寸分布：小目标 {size['counts']['small']} 个、中目标 {size['counts']['medium']} 个、"
            f"大目标 {size['counts']['large']} 个；IoU>0.5 的重叠对 "
            f"{stats['overlap']['pairs_iou_gt_0_5']} 对（抽样 {stats['overlap']['sampled']} 个）。"
        ),
        limitations=(
            "本报告为 Mock 模式，未调用 LLM，仅用于验证报告结构与数据链路，"
            "不能作为真实分析结论。未提供 ground truth/mAP，无法判断模型真实精度；"
            "密度等级与尺寸分类均为启发式阈值。"
        ),
        conclusion=(
            f"本任务共 {total} 个目标，主要类别为"
            f"{next(iter(classes), '无') if classes else '无'}，"
            f"目标主要分布在{grid['dominant']}。以上数字均来自检测框统计。"
        ),
    )


def _build_markdown(sections: AnalysisSections) -> str:
    lines = []
    for index, (field, title) in enumerate(SECTION_TITLES, start=1):
        lines.append(f"## {index}. {title}")
        lines.append("")
        lines.append(getattr(sections, field).strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _latest_report(session: Session, task_id: str) -> Optional[LLMReport]:
    return session.execute(
        select(LLMReport)
        .where(LLMReport.task_id == task_id)
        .order_by(LLMReport.created_at.desc(), LLMReport.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _to_response(report: LLMReport) -> AnalysisReportResponse:
    structured = AnalysisSections.model_validate(report.structured or {})
    return AnalysisReportResponse(
        report_id=report.id,
        task_id=report.task_id,
        model_name=report.model_name,
        prompt_version=report.prompt_version,
        content=report.content,
        structured=structured,
        latency_ms=report.latency_ms,
        usage=AnalysisUsage(
            prompt_tokens=report.prompt_tokens or 0,
            completion_tokens=report.completion_tokens or 0,
        ),
        is_mock=report.is_mock,
        created_at=report.created_at,
    )


def get_report(session: Session, task_id: str) -> AnalysisReportResponse:
    get_task(session, task_id)
    report = _latest_report(session, task_id)
    if report is None:
        raise AppError(
            "ANALYSIS_NOT_FOUND",
            "该任务还没有分析报告",
            404,
            {"task_id": task_id},
        )
    return _to_response(report)


async def generate_report(
    session: Session,
    task_id: str,
    settings: Settings,
    force: bool = False,
) -> AnalysisReportResponse:
    task = get_task(session, task_id)
    if task.status != "success":
        raise AppError(
            "TASK_NOT_READY",
            "只有成功完成的检测任务才能生成分析报告",
            409,
            {"task_id": task_id, "status": task.status},
        )

    if not force:
        existing = _latest_report(session, task_id)
        if existing is not None:
            return _to_response(existing)

    results = (
        session.execute(
            select(DetectionResult)
            .where(DetectionResult.task_id == task_id)
            .order_by(DetectionResult.confidence.desc())
        )
        .scalars()
        .all()
    )
    facts = _build_facts(task, list(results))

    if settings.llm_mock:
        sections = _mock_sections(facts)
        model_name = "llm-mock"
        latency_ms = 0
        prompt_tokens = 0
        completion_tokens = 0
        is_mock = True
    else:
        if not settings.llm_configured:
            raise AppError(
                "LLM_NOT_CONFIGURED",
                "LLM 未配置，请设置 LLM_API_KEY 与 LLM_MODEL",
                503,
            )
        sections, result = await _generate_with_llm(settings, facts)
        model_name = result.model
        latency_ms = result.latency_ms
        prompt_tokens = result.prompt_tokens
        completion_tokens = result.completion_tokens
        is_mock = False

    content = _build_markdown(sections)
    report = LLMReport(
        task_id=task_id,
        report_type="detection_analysis",
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        content=content,
        structured=sections.model_dump(),
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        is_mock=is_mock,
    )
    try:
        session.add(report)
        session.commit()
        session.refresh(report)
    except Exception:
        session.rollback()
        raise

    logger.info(
        "Analysis report %s for task %s model=%s mock=%s latency=%dms",
        report.id,
        task_id,
        model_name,
        is_mock,
        latency_ms,
    )
    return _to_response(report)
