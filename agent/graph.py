import os
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.tools import get_current_datetime, calculate_expression, web_search
import config
from utils.logger import get_logger

logger = get_logger("agent.graph")

# Define state structure
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Register tools
tools = [get_current_datetime, calculate_expression, web_search]
tool_node = ToolNode(tools)

# Initialize Gemini Chat Model
# Using 'gemini-2.5-flash' which is the recommended model for function calling and reasoning on the free tier.
model = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    google_api_key=config.GEMINI_API_KEY,
    temperature=0.7,
).bind_tools(tools)

# Define agent node
async def call_model(state: AgentState):
    """Invokes the model with the current conversation history state."""
    messages = state["messages"]
    
    # Prepend a system message to guide the agent to use conversation history
    system_msg = SystemMessage(
        content=(
            "You are an advanced Agentic AI Telegram chatbot. You have access to tools and "
            "you have persistent memory of the current conversation history. Always use the "
            "conversation history to remember details about the user (such as their name) "
            "and maintain context across multiple turns. Do not tell the user that you "
            "cannot remember things or that you don't have memory, because you are running "
            "in a stateful session and can see the history of this thread."
        )
    )
    
    # Prepend system message to the history list sent to Gemini
    messages_to_send = [system_msg] + list(messages)
    
    logger.info(f"Invoking model with {len(messages_to_send)} messages (including system instruction).")
    response = await model.ainvoke(messages_to_send)
    return {"messages": [response]}

# Define conditional route logic
def should_continue(state: AgentState):
    """Determines whether the graph should transition to 'tools' or end the execution."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the model made tool calls, route to the tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"Model requested tool calls: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tools"
        
    # If no tool calls, finish the execution
    logger.info("No tool calls requested. Finishing loop.")
    return "end"

# Construct State Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# Set entry point
workflow.set_entry_point("agent")

# Add conditional routing
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

# Route tools back to agent for the next turn
workflow.add_edge("tools", "agent")

async def get_agent_graph():
    """
    Compiles and returns the LangGraph workflow along with its AsyncSqliteSaver checkpointer.
    The caller is responsible for calling checkpointer.__aexit__() on shutdown.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "checkpoints.db")
    
    logger.info(f"Initializing AsyncSqliteSaver checkpointer at {db_path}")
    checkpointer_context = AsyncSqliteSaver.from_conn_string(db_path)
    memory = await checkpointer_context.__aenter__()
    
    # Compile graph with persistence
    compiled_graph = workflow.compile(checkpointer=memory)
    return compiled_graph, checkpointer_context
