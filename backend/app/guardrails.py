import re
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger("voice-agent")

def luhn_check(card_num: str) -> bool:
    """Verifies card number using Luhn algorithm."""
    digits = [int(c) for c in card_num if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0

class GuardrailService:
    def __init__(self):
        # Regex patterns for sensitive data
        self.patterns = {
            "credit_card": re.compile(r'\b(?:\d[ -]*?){13,19}\b'),
            "ssn": re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b'),
            "password_pattern": re.compile(r'(?i)\b(?:password|passcode|pin|secret|api[_-]?key)\s*[:=]\s*(\S+)\b'),
        }

        # Common prompt injection / jailbreak phrases
        self.injection_phrases = [
            "ignore all previous instructions",
            "ignore previous instructions",
            "forget your system prompt",
            "disregard safety guidelines",
            "system prompt reveal",
            "you are now in developer mode",
            "dan mode",
            "override instructions",
            "act as an unrestricted"
        ]

    def sanitize_text(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Sanitizes text by masking sensitive information (Credit Cards, SSN, Secrets).
        Returns (sanitized_text, redaction_logs).
        """
        if not text:
            return text, []

        sanitized = text
        logs = []

        # 1. Check SSN
        for match in self.patterns["ssn"].finditer(text):
            val = match.group(0)
            clean_digits = re.sub(r'\D', '', val)
            if len(clean_digits) == 9:
                sanitized = sanitized.replace(val, "[REDACTED_SSN]")
                logs.append({"type": "SSN", "original_len": len(val)})

        # 2. Check Credit Cards
        for match in self.patterns["credit_card"].finditer(text):
            val = match.group(0)
            clean_digits = re.sub(r'\D', '', val)
            if luhn_check(clean_digits):
                sanitized = sanitized.replace(val, "[REDACTED_CREDIT_CARD]")
                logs.append({"type": "CREDIT_CARD", "last4": clean_digits[-4:]})

        # 3. Check Passwords & Secrets
        for match in self.patterns["password_pattern"].finditer(text):
            val = match.group(0)
            secret_val = match.group(1)
            sanitized = sanitized.replace(secret_val, "********")
            logs.append({"type": "SENSITIVE_SECRET", "masked": "********"})

        if logs:
            logger.info(f"Guardrails active: Sanitized {len(logs)} sensitive items from text.")

        return sanitized, logs

    def check_prompt_injection(self, text: str) -> Tuple[bool, str]:
        """
        Checks if the input text contains prompt injection or jailbreak attempts.
        Returns (is_injection, deflection_message).
        """
        if not text:
            return False, ""

        clean_input = text.lower().strip()
        for phrase in self.injection_phrases:
            if phrase in clean_input:
                logger.warning(f"Guardrails trigger: Prompt injection detected ('{phrase}')")
                return True, "I am an AI voice assistant designed to help with appointments and home services. How can I assist you with your booking or inquiry today?"

        return False, ""

guardrail_service = GuardrailService()
