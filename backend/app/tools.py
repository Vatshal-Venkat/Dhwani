import logging
from typing import Dict, Any, List
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Booking, Lead

logger = logging.getLogger("voice-agent")

# Function Schemas for LLM Tool Registration
AVAILABLE_TOOLS = [
    {
        "name": "check_availability",
        "description": "Checks available appointment time slots for a given service and date.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service_type": {
                    "type": "STRING",
                    "description": "Type of service, e.g., 'SmartHome Installation', 'HVAC Maintenance', 'Consultation'"
                },
                "date": {
                    "type": "STRING",
                    "description": "Date in YYYY-MM-DD format or relative term like 'tomorrow', 'next Monday'"
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "create_booking",
        "description": "Creates and confirms a new appointment booking for the customer in the database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_name": {
                    "type": "STRING",
                    "description": "Full name of the customer"
                },
                "customer_phone": {
                    "type": "STRING",
                    "description": "Phone number of the customer"
                },
                "service_type": {
                    "type": "STRING",
                    "description": "Type of service requested"
                },
                "date": {
                    "type": "STRING",
                    "description": "Booking date (e.g., '2026-07-25')"
                },
                "time_slot": {
                    "type": "STRING",
                    "description": "Time slot requested (e.g., '10:00 AM', '02:00 PM')"
                },
                "notes": {
                    "type": "STRING",
                    "description": "Additional customer notes or installation address"
                }
            },
            "required": ["customer_name", "date", "time_slot"]
        }
    },
    {
        "name": "cancel_booking",
        "description": "Cancels an existing booking by booking ID or customer phone number.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "booking_id": {
                    "type": "INTEGER",
                    "description": "The numeric ID of the booking to cancel"
                },
                "customer_phone": {
                    "type": "STRING",
                    "description": "Customer phone number associated with the booking"
                }
            }
        }
    },
    {
        "name": "capture_lead",
        "description": "Saves potential customer interest and inquiry details as a new Lead in the database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Customer name"
                },
                "phone": {
                    "type": "STRING",
                    "description": "Customer contact phone"
                },
                "intent": {
                    "type": "STRING",
                    "description": "Summary of what product/service the customer is interested in"
                }
            },
            "required": ["name", "phone"]
        }
    },
    {
        "name": "transfer_to_human",
        "description": "Initiates a live transfer to a real human customer representative when the user asks for a real person or confirms they want to be connected to a human.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "reason": {
                    "type": "STRING",
                    "description": "Reason for human transfer (e.g., 'customer dissatisfied', 'explicit human request', 'complex issue')"
                },
                "department": {
                    "type": "STRING",
                    "description": "Target department for transfer (e.g., 'Senior Customer Support', 'Technical Specialist')"
                }
            },
            "required": ["reason"]
        }
    }
]

async def execute_tool(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a requested tool function asynchronously against the database.
    """
    logger.info(f"Tool Execution Requested: {function_name} with args: {arguments}")
    
    async with AsyncSessionLocal() as db:
        try:
            if function_name == "check_availability":
                service = arguments.get("service_type", "SmartHome Installation")
                date = arguments.get("date", "tomorrow")
                
                # Fetch existing bookings on date to find open slots
                stmt = select(Booking.booking_time).where(Booking.booking_date == date, Booking.status == "confirmed")
                res = await db.execute(stmt)
                booked_slots = set(res.scalars().all())
                
                all_slots = ["09:00 AM", "10:00 AM", "11:30 AM", "02:00 PM", "04:00 PM"]
                available = [slot for slot in all_slots if slot not in booked_slots]
                
                return {
                    "status": "success",
                    "service": service,
                    "date": date,
                    "available_slots": available if available else ["02:00 PM (Emergency Slot)"],
                    "message": f"Found {len(available)} available slots for {date}."
                }

            elif function_name == "create_booking":
                name = arguments.get("customer_name", "Valued Customer")
                phone = arguments.get("customer_phone", "555-0199")
                service = arguments.get("service_type", "SmartHome Installation")
                date = arguments.get("date", "tomorrow")
                time_slot = arguments.get("time_slot", "10:00 AM")
                notes = arguments.get("notes", "")

                new_booking = Booking(
                    customer_name=name,
                    customer_phone=phone,
                    service_type=service,
                    booking_date=date,
                    booking_time=time_slot,
                    status="confirmed",
                    notes=notes
                )
                db.add(new_booking)
                await db.commit()
                await db.refresh(new_booking)

                return {
                    "status": "success",
                    "booking_id": new_booking.id,
                    "customer_name": name,
                    "date": date,
                    "time_slot": time_slot,
                    "confirmation": f"CONF-{new_booking.id:04d}",
                    "message": f"Successfully created booking #{new_booking.id} for {name} on {date} at {time_slot}."
                }

            elif function_name == "cancel_booking":
                booking_id = arguments.get("booking_id")
                phone = arguments.get("customer_phone")
                
                if booking_id:
                    stmt = select(Booking).where(Booking.id == booking_id)
                elif phone:
                    stmt = select(Booking).where(Booking.customer_phone == phone).order_by(Booking.id.desc())
                else:
                    return {"status": "error", "message": "Please provide booking_id or customer_phone."}

                res = await db.execute(stmt)
                booking = res.scalar_one_or_none()
                if not booking:
                    return {"status": "error", "message": "No matching active booking found to cancel."}

                booking.status = "cancelled"
                await db.commit()
                return {
                    "status": "success",
                    "booking_id": booking.id,
                    "message": f"Booking #{booking.id} for {booking.customer_name} has been cancelled."
                }

            elif function_name == "capture_lead":
                name = arguments.get("name", "Unknown")
                phone = arguments.get("phone", "N/A")
                intent = arguments.get("intent", "Inquiry")

                new_lead = Lead(
                    name=name,
                    phone=phone,
                    intent=intent,
                    status="new"
                )
                db.add(new_lead)
                await db.commit()
                await db.refresh(new_lead)

                return {
                    "status": "success",
                    "lead_id": new_lead.id,
                    "message": f"Lead for {name} recorded successfully."
                }

            elif function_name == "transfer_to_human":
                reason = arguments.get("reason", "Customer requested human support or expressed dissatisfaction")
                dept = arguments.get("department", "Senior Customer Support")
                target_phone = "+1-800-555-0199"

                logger.info(f"Human Transfer Tool Executed: Department='{dept}', Reason='{reason}'")

                return {
                    "status": "success",
                    "action": "human_transfer",
                    "transfer_triggered": True,
                    "department": dept,
                    "target_phone": target_phone,
                    "reason": reason,
                    "message": f"Initiating live transfer to {dept} ({target_phone}). Please hold on while I connect your call."
                }

            else:
                return {"status": "error", "message": f"Unknown tool: {function_name}"}

        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}")
            return {"status": "error", "message": f"Execution error: {str(e)}"}
