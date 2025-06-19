from typing import Optional

from crewai.utilities.events import (
    CrewKickoffCompletedEvent,
    ToolUsageErrorEvent,
    ToolUsageStartedEvent,
    ToolUsageFinishedEvent,
)
from crewai.utilities.events.base_event_listener import BaseEventListener
from crewai.utilities.events.crew_events import CrewKickoffStartedEvent
from crewai.utilities.events.task_events import TaskEvaluationEvent

try:
    import agentops

    AGENTOPS_INSTALLED = True
except ImportError:
    AGENTOPS_INSTALLED = False

from rich.console import Console
from rich.panel import Panel
import os

DEBUG_CREWAI = True
console = Console()


class AgentOpsListener(BaseEventListener):
    tool_event: Optional["agentops.ToolEvent"] = None
    session: Optional["agentops.Session"] = None

    def __init__(self):
        super().__init__()

    def setup_listeners(self, crewai_event_bus):
        if not AGENTOPS_INSTALLED:
            return

        @crewai_event_bus.on(CrewKickoffStartedEvent)
        def on_crew_kickoff_started(source, event: CrewKickoffStartedEvent):
            self.session = agentops.init()
            for agent in source.agents:
                if self.session:
                    self.session.create_agent(
                        name=agent.role,
                        agent_id=str(agent.id),
                    )

        @crewai_event_bus.on(CrewKickoffCompletedEvent)
        def on_crew_kickoff_completed(source, event: CrewKickoffCompletedEvent):
            if self.session:
                self.session.end_session(
                    end_state="Success",
                    end_state_reason="Finished Execution",
                )

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_usage_started(source, event: ToolUsageStartedEvent):
            # 创建并上报工具调用开始事件，包含输入参数
            self.tool_event = agentops.ToolEvent(name=event.tool_name, args=event.tool_args)
            
            if self.session:
                self.session.record(self.tool_event)
                if DEBUG_CREWAI:
                    console.print(Panel(str(event.tool_args), title=f"【工具调用入参】 {event.tool_name}", expand=False, style="bold blue"))

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_usage_finished(source, event: ToolUsageFinishedEvent):
            # 记录工具调用完成信息，包含输出和时间等
            if self.tool_event:
                # 更新 tool_event 属性
                self.tool_event.args = event.tool_args
                self.tool_event.result = event.output
                self.tool_event.metadata = {
                    "from_cache": event.from_cache,
                    "started_at": event.started_at.isoformat(),
                    "finished_at": event.finished_at.isoformat(),
                }
            if self.session:
                self.session.record(self.tool_event)
                if DEBUG_CREWAI:
                    console.print(Panel(str(event.output), title=f"【工具调用结果】 {event.tool_name}", expand=False, style="bold green"))

        @crewai_event_bus.on(ToolUsageErrorEvent)
        def on_tool_usage_error(source, event: ToolUsageErrorEvent):
            if DEBUG_CREWAI:
                console.print(Panel(str(event.error), title=f"【工具调用异常】 {event.tool_name}", expand=False, style="bold red"))
            agentops.ErrorEvent(exception=event.error, trigger_event=self.tool_event)

        @crewai_event_bus.on(TaskEvaluationEvent)
        def on_task_evaluation(source, event: TaskEvaluationEvent):
            if self.session:
                self.session.create_agent(
                    name="Task Evaluator", agent_id=str(source.original_agent.id)
                )


agentops_listener = AgentOpsListener()
