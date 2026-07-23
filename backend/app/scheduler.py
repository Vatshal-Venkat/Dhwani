import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ScheduledCall
from app.twilio_utils import execute_outbound_call

logger = logging.getLogger("voice-agent")

# Initialize APScheduler for the FastAPI AsyncIO event loop
scheduler = AsyncIOScheduler()

async def poll_scheduled_calls():
    """
    Periodic job that checks the database for calls that are due to be triggered.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Query all pending calls where scheduled_time is less than or equal to current time
            stmt = select(ScheduledCall).where(
                ScheduledCall.status == "pending",
                ScheduledCall.scheduled_time <= datetime.now(timezone.utc)
            )
            result = await session.execute(stmt)
            due_calls = result.scalars().all()
            
            for call in due_calls:
                logger.info(f"Background campaign: Processing scheduled call ID={call.id} to {call.phone_number}")
                
                # Mark as processing immediately to prevent duplicate runs
                call.status = "processing"
                await session.commit()
                
                # Retrieve webhook callback base URL
                public_url = call.public_url or settings.PUBLIC_URL
                if not public_url:
                    logger.error(f"Cannot trigger scheduled call {call.id}: PUBLIC_URL is not configured.")
                    call.status = "failed"
                    call.error_message = "PUBLIC_URL configuration missing."
                    await session.commit()
                    continue
                
                try:
                    # Execute Twilio outbound REST API request
                    call_sid = await execute_outbound_call(
                        phone_number=call.phone_number,
                        agent_id=call.agent_id,
                        public_url=public_url
                    )
                    # Update status to completed on successful Twilio trigger
                    call.status = "completed"
                    logger.info(f"Successfully triggered scheduled call ID={call.id} (SID: {call_sid})")
                except Exception as e:
                    # Log failure details and increment retry count
                    call.status = "failed"
                    call.retry_count += 1
                    call.error_message = str(e)[:250]
                    logger.error(f"Failed triggering scheduled call ID={call.id}: {e}")
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error occurred in background scheduled call poller: {e}")

def start_scheduler():
    """
    Start the background scheduler and register the polling job.
    """
    if not scheduler.running:
        scheduler.add_job(
            poll_scheduled_calls,
            "interval",
            seconds=10,
            id="campaign_manager_poller",
            replace_existing=True
        )
        scheduler.start()
        logger.info("Outbound Campaign Scheduler started (polling interval: 10s)")

def shutdown_scheduler():
    """
    Shutdown the background scheduler cleanly.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Outbound Campaign Scheduler stopped.")
