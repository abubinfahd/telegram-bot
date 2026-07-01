import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment
load_dotenv()

# We temporarily bypass config.py validation for the Telegram token since this script only tests the Gemini Agent layer
# Let's mock the TELEGRAM_BOT_TOKEN if missing to allow importing config
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    os.environ["TELEGRAM_BOT_TOKEN"] = "mock_telegram_token_for_agent_test"

import config
from agent.graph import get_agent_graph
from utils.logger import get_logger

logger = get_logger("test_agent")

def clean_response(content):
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)
    return str(content)

async def run_test():
    # Verify Gemini API key
    if not config.GEMINI_API_KEY or "your_gemini_api_key_here" in config.GEMINI_API_KEY:
        print("⚠️  GEMINI_API_KEY is not set or is still a placeholder.")
        print("Please configure GEMINI_API_KEY in a '.env' file in the root directory to run this test.")
        return

    # Delete old database if exists to ensure clean starting state for the test
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "checkpoints.db")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("🧹 Cleared old test database.")
        except Exception as e:
            print(f"⚠️  Could not clear test database: {e}")

    print("🚀 Initializing LangGraph Agent...")
    graph, checkpointer = await get_agent_graph()
    
    # We will run a test thread conversation
    thread_id = "test-thread-12345"
    graph_config = {"configurable": {"thread_id": thread_id}}
    
    # Message 1: Conversational / Memory Check
    print("\n--- Test 1: Setting Name (Memory Check) ---")
    user_input = "Hello! My name is Charlie. Remember my name."
    print(f"User: {user_input}")
    
    try:
        result = await graph.ainvoke(
            {"messages": [("user", user_input)]},
            config=graph_config
        )
        response = clean_response(result["messages"][-1].content)
        print(f"Agent: {response}")
        
        # Message 2: Tool execution (Date/Time & Calculation)
        print("\n--- Test 2: Date and Calculation Tool (Agentic Check) ---")
        user_input = "What year is it currently, and what is the value of (2026 - 1998) * 4?"
        print(f"User: {user_input}")
        
        result = await graph.ainvoke(
            {"messages": [("user", user_input)]},
            config=graph_config
        )
        # Iterate and show steps/messages if wanted
        response = clean_response(result["messages"][-1].content)
        print(f"Agent: {response}")
        
        # Message 3: Web Search Tool
        print("\n--- Test 3: Web Search Tool (Agentic Check) ---")
        user_input = "Search for the latest news on NASA Artemis mission."
        print(f"User: {user_input}")
        
        result = await graph.ainvoke(
            {"messages": [("user", user_input)]},
            config=graph_config
        )
        response = clean_response(result["messages"][-1].content)
        print(f"Agent: {response}")
        
        # Message 4: Recalling Name (Memory persistence verification)
        print("\n--- Test 4: Recalling Name (Memory Retrieval) ---")
        user_input = "What was my name again?"
        print(f"User: {user_input}")
        
        result = await graph.ainvoke(
            {"messages": [("user", user_input)]},
            config=graph_config
        )
        response = clean_response(result["messages"][-1].content)
        print(f"Agent: {response}")
        
    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
    finally:
        await checkpointer.__aexit__(None, None, None)
        print("\nTest run finished. SQLite checkpointer closed.")

if __name__ == "__main__":
    asyncio.run(run_test())
