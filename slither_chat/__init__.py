"""slither-chat: your smart-contract audit copilot.

Runs Slither, then explains every finding in plain English — from an offline
knowledge base, a Hugging Face zero-shot model, or any LLM — with suggested
patches and a benchmark mode that scores your pipeline against real audited
contracts from the Hugging Face Hub.
"""

__version__ = "0.3.0"

from .models import AuditResult, Finding, Severity  # noqa: F401
from .pipeline import audit  # noqa: F401