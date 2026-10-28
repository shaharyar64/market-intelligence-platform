import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.schedules import (
    InstagramSchedule,
    InstagramScheduleCreate,
    InstagramScheduleUpdate,
    ScheduleRunAccepted,
)
from services.data_scraping_service.app.services.scheduler import (
    create_schedule,
    delete_schedule,
    execute_schedule,
    get_schedule,
    list_schedules,
    mark_started,
    update_schedule,
)


router = APIRouter(prefix="/instagram/schedules", tags=["Instagram Scheduler"])


@router.post("", response_model=InstagramSchedule, status_code=status.HTTP_201_CREATED)
async def create(data: InstagramScheduleCreate) -> InstagramSchedule:
    return InstagramSchedule.model_validate(await asyncio.to_thread(create_schedule, data))


@router.get("", response_model=list[InstagramSchedule])
async def list_all() -> list[InstagramSchedule]:
    rows = await asyncio.to_thread(list_schedules)
    return [InstagramSchedule.model_validate(row) for row in rows]


@router.get("/{schedule_id}", response_model=InstagramSchedule)
async def get_one(schedule_id: UUID) -> InstagramSchedule:
    row = await asyncio.to_thread(get_schedule, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return InstagramSchedule.model_validate(row)


@router.patch("/{schedule_id}", response_model=InstagramSchedule)
async def update(schedule_id: UUID, data: InstagramScheduleUpdate) -> InstagramSchedule:
    row = await asyncio.to_thread(update_schedule, schedule_id, data)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return InstagramSchedule.model_validate(row)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(schedule_id: UUID) -> None:
    if not await asyncio.to_thread(delete_schedule, schedule_id):
        raise HTTPException(status_code=404, detail="Schedule not found")


@router.post("/{schedule_id}/run", response_model=ScheduleRunAccepted, status_code=202)
async def run_now(schedule_id: UUID, background_tasks: BackgroundTasks) -> ScheduleRunAccepted:
    row = await asyncio.to_thread(get_schedule, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await asyncio.to_thread(mark_started, schedule_id)
    background_tasks.add_task(execute_schedule, row)
    return ScheduleRunAccepted(schedule_id=str(schedule_id))
