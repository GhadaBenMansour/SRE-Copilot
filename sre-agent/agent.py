"""
SRE Copilot Agent — LangChain ReAct agent powered by Ollama/Mistral.

Flow:
1. Receive alert payload
2. Investigate with kubectl tools
3. Classify root cause using Mistral
4. Generate runbook
5. Optionally create GitOps PR + trigger ArgoCD sync
"""
import asyncio
import logging
import os
from functools import partial
from typing import Optional

from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from tools import ALL_TOOLS
from models import Alert, AgentResponse, RemediationStep

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "false").lower() == "true"

# ─────────────────────────────────────────────
# System prompt for the SRE agent
# ─────────────────────────────────────────────
SRE_SYSTEM_PROMPT = """You are an SRE AI. Investigate Kubernetes alerts and return a JSON diagnosis.

Tools available:
{tools}

Tool names: {tool_names}

STRICT RULES:
- Tool inputs must NEVER have quotes. Use: demo/crash-app NOT 'demo/crash-app'
- Use get_pod_status first to find the exact pod name, then use that name for logs/describe.
- Do at most 4 tool calls, then give Final Answer.
- Final Answer must be valid JSON only, no text before or after.

Format:
Thought: reason
Action: tool_name
Action Input: input_without_quotes
Observation: result
Thought: I have enough info.
Final Answer: {{"classification":"...","root_cause":"...","runbook":[{{"order":1,"action":"...","command":"...","description":"..."}}],"auto_remediation_applied":false,"remediation_details":"...","git_pr_url":null,"argocd_sync_triggered":false}}

Alert:
{input}

{agent_scratchpad}"""


def build_agent_executor() -> AgentExecutor:
    """Build and return the LangChain ReAct agent."""
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        temperature=0.1,
        num_predict=4096,
    )

    prompt = PromptTemplate(
        input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
        template=SRE_SYSTEM_PROMPT,
    )

    agent = create_react_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)

    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


async def run_sre_investigation(alert: Alert) -> AgentResponse:
    """
    Main entry point: takes a single alert and returns a structured AgentResponse.
    """
    # Build context string for the agent
    alert_context = f"""
Alert Name: {alert.labels.alertname}
Severity: {alert.labels.severity}
Status: {alert.status}
Namespace: {alert.labels.namespace}
Pod: {alert.labels.pod or 'unknown'}
Deployment: {alert.labels.deployment or 'unknown'}
Summary: {alert.annotations.summary}
Description: {alert.annotations.description}
Started At: {alert.startsAt or 'unknown'}
AUTO_REMEDIATE: {AUTO_REMEDIATE}
""".strip()

    investigation_log = []

    try:
        executor = build_agent_executor()
        # Run the synchronous blocking call in a thread pool so it doesn't
        # block the asyncio event loop (which would cause port-forward timeouts)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, partial(executor.invoke, {"input": alert_context})
        )

        # Collect intermediate steps for audit log
        for step in result.get("intermediate_steps", []):
            action, observation = step
            investigation_log.append(
                f"[{action.tool}] Input: {str(action.tool_input)[:200]}"
            )
            investigation_log.append(f"  → {str(observation)[:300]}")

        # Parse Final Answer JSON
        raw_output = result.get("output", "{}")
        import json, re

        # Extract JSON block from the output
        json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {}

        # Build runbook steps
        runbook = [
            RemediationStep(**step) for step in parsed.get("runbook", [])
        ] or [
            RemediationStep(
                order=1,
                action="Manual Investigation Required",
                description="The agent could not determine a structured runbook. Review pod logs manually.",
            )
        ]

        return AgentResponse(
            alert_name=alert.labels.alertname,
            namespace=alert.labels.namespace or "default",
            severity=alert.labels.severity or "unknown",
            classification=parsed.get("classification", "Unknown"),
            root_cause=parsed.get("root_cause", raw_output[:500]),
            runbook=runbook,
            auto_remediation_applied=parsed.get("auto_remediation_applied", False),
            remediation_details=parsed.get("remediation_details"),
            git_pr_url=parsed.get("git_pr_url"),
            argocd_sync_triggered=parsed.get("argocd_sync_triggered", False),
            investigation_log=investigation_log,
        )

    except Exception as e:
        logger.exception("Agent execution failed")
        return AgentResponse(
            alert_name=alert.labels.alertname,
            namespace=alert.labels.namespace or "default",
            severity=alert.labels.severity or "unknown",
            classification="Unknown",
            root_cause=f"Agent error: {str(e)}",
            runbook=[
                RemediationStep(
                    order=1,
                    action="Manual Investigation",
                    description=f"Agent failed with error: {str(e)}",
                )
            ],
            auto_remediation_applied=False,
            investigation_log=investigation_log,
        )
