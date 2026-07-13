"""Agent Layer exceptions."""
from __future__ import annotations
class AgentError(Exception): pass
class AgentInitializationError(AgentError): pass
class AgentExecutionError(AgentError): pass
class ToolExecutionError(AgentError): pass
class ContextBuildError(AgentError): pass
class AgentNotFoundError(AgentError): pass
class AgentNotReadyError(AgentError): pass