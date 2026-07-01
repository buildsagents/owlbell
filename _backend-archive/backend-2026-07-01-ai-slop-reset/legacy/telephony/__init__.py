"""telephony - Owlbell telephony subsystem.

Connects FreeSWITCH (SIP/RTP) to the AI conversation pipeline via ESL.
"""
from legacy.telephony.manager import TelephonyManager
from legacy.telephony.core.esl_connection import ESLConnection, ESLEvent
from legacy.telephony.core.call_handler import CallHandler

__all__ = ["TelephonyManager", "ESLConnection", "ESLEvent", "CallHandler"]
