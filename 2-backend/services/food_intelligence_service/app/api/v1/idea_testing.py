import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from services.food_intelligence_service.app.api.deps import get_current_user
from services.food_intelligence_service.app.api.errors import internal_error
from services.food_intelligence_service.app.assistant.agent import embed_query
from services.food_intelligence_service.app.idea_testing import store
from services.food_intelligence_service.app.idea_testing.extraction import extract_concept
from services.food_intelligence_service.app.idea_testing.usage import run_with_usage, with_totals
from services.food_intelligence_service.app.idea_testing.service import (
    MAX_COMPARE_CONCEPTS,
    ComparisonNotFoundError,
    ConceptNotFoundError,
    ConceptOutdatedError,
    InsufficientEvidenceError,
    assess_and_compare,
    get_comparison_by_id,
    list_history,
    shape_assessment,
)
from services.food_intelligence_service.app.services import trend_service

router = APIRouter(prefix="/idea-testing", tags=["Idea Testing"])

Country = Literal["SA", "AE"]
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
_PDF_TYPE = "application/pdf"
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024

_DASHBOARD_NAMES = {"real_estate": "Real Estate"}


def _out_of_scope_message(extracted) -> str | None:
    if extracted.input_kind == "other_text":
        return ("We couldn't find a concept to test in this input. Describe the idea: what it "
                "is, who it is for and what it promises.")
    if extracted.food_relation == "not_food":
        message = (f"This is about {extracted.subject}, not a food or beverage concept. "
                   "Idea Testing on this dashboard scores food and beverage concepts only.")
        dashboard = _DASHBOARD_NAMES.get(extracted.related_dashboard)
        if dashboard:
            message += f" Try Idea Testing on the {dashboard} dashboard instead."
        return message
    if extracted.input_kind == "question":
        return (f"This reads as a question about {extracted.subject} rather than a concept to "
                "test. Describe the idea itself: what it is, who it is for and what it promises.")
    return None


@router.post("/concepts")
async def create_concept(
    title: str = Form(...),
    raw_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if not raw_text and file is None:
        raise HTTPException(status_code=400, detail="Provide raw_text or a file.")

    try:
        if file is not None:
            data = await file.read()
            if len(data) > _MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=400, detail="File too large.")

            if file.content_type in _IMAGE_TYPES:
                input_format = "image"
                extract_args = (raw_text, data, file.content_type, None)
            elif file.content_type == _PDF_TYPE:
                input_format = "pdf"
                extract_args = (raw_text, None, None, data)
            else:
                raise HTTPException(status_code=400,
                                    detail=f"Unsupported file type: {file.content_type}")

            try:
                extracted, usage = await run_in_threadpool(
                    run_with_usage, extract_concept, *extract_args, title=title)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400,
                                    detail="Could not read the uploaded file.") from None

            # The uploaded file is scored directly from these in-memory bytes above
            # and never read again, so it is not archived to S3 -- no downstream
            # code reads idea_concepts.file_s3_key.
            file_key = None
        else:
            file_key = None
            extracted, usage = await run_in_threadpool(
                run_with_usage, extract_concept, raw_text, title=title)
            input_format = "text"
    except HTTPException:
        raise
    except Exception:
        raise internal_error("idea_testing_create_concept") from None

    rejection = _out_of_scope_message(extracted)
    if rejection:
        raise HTTPException(status_code=422, detail=rejection)

    concept_id = uuid.uuid4().hex
    await run_in_threadpool(
        store.save_concept, concept_id, current_user["username"], title, input_format,
        raw_text, file_key, extracted.model_dump(), with_totals({"llm": usage}))
    return {"concept_id": concept_id, "extracted": extracted.model_dump()}


class AssessRequest(BaseModel):
    concept_ids: list[str] = Field(min_length=1, max_length=3)
    mode: Literal["single", "multiple"]
    test_type: Literal["quick-idea", "advertising", "innovation"]
    country: Country | None = None


@router.post("/assess")
async def assess(body: AssessRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    if len(body.concept_ids) > MAX_COMPARE_CONCEPTS:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot compare more than {MAX_COMPARE_CONCEPTS} concepts "
                   f"(got {len(body.concept_ids)}).")
    try:
        run_id = await run_in_threadpool(trend_service.latest_run_id, body.country)
        result = await run_in_threadpool(
            assess_and_compare, body.concept_ids, body.test_type, run_id, body.country,
            embed_query)
    except ConceptNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except (InsufficientEvidenceError, ConceptOutdatedError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except Exception:
        raise internal_error("idea_testing_assess") from None
    return result


async def _owns_concept(concept_id: str, username: str) -> bool:
    concept = await run_in_threadpool(store.get_concept, concept_id)
    return concept is not None and concept["created_by"] == username


@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str,
                         current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        row = await run_in_threadpool(store.get_assessment, assessment_id)
        owns = await _owns_concept(row["concept_id"], current_user["username"]) if row else False
    except Exception:
        raise internal_error("idea_testing_get_assessment") from None
    if row is None or not owns:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return shape_assessment(row, cached=False)


@router.get("/history")
async def get_history(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        items = await run_in_threadpool(list_history, current_user["username"])
    except Exception:
        raise internal_error("idea_testing_get_history") from None
    return {"items": items}


@router.get("/comparisons/{comparison_id}")
async def get_comparison(comparison_id: str,
                         current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        result = await run_in_threadpool(get_comparison_by_id, comparison_id)
        for a in result["assessments"]:
            if not await _owns_concept(a["concept_id"], current_user["username"]):
                raise ComparisonNotFoundError(comparison_id)
    except ComparisonNotFoundError:
        raise HTTPException(status_code=404, detail="Comparison not found.") from None
    except Exception:
        raise internal_error("idea_testing_get_comparison") from None
    return result
