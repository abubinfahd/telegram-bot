import os
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import config
from utils.logger import get_logger
from agent.graph import get_agent_graph

logger = get_logger("main")

# Global references to be loaded on post_init
graph = None
checkpointer = None

async def post_init(application):
    """Initializes the LangGraph agent and its checkpointer asynchronously."""
    global graph, checkpointer
    logger.info("Initializing Agent Graph asynchronously...")
    graph, checkpointer = await get_agent_graph()
    logger.info("Agent Graph initialized successfully.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    welcome_text = (
        "🤖 **Welcome to the Agentic AI Bot!**\n\n"
        "I am an intelligent assistant powered by Google's **Gemini 2.5 Flash** and **LangGraph**.\n\n"
        "**Here is what I can do:**\n"
        "📅 Get the current date and time.\n"
        "🧮 Safely compute complex mathematical calculations.\n"
        "🔍 Search the web for up-to-date information and news.\n\n"
        "**Available Commands:**\n"
        "/start - Show this message\n"
        "/clear - Reset our conversation history\n\n"
        "Just send me a message to get started!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets conversation memory by deleting checkpoints from SQLite database."""
    chat_id = update.effective_chat.id
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "checkpoints.db")
    
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Clear checkpoints and writes for the thread
            cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (str(chat_id),))
            cursor.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (str(chat_id),))
            conn.commit()
            conn.close()
            logger.info(f"Cleared checkpoints for thread_id/chat_id {chat_id}")
            
        await update.message.reply_text("🧹 Conversation history cleared! We are starting fresh.")
    except Exception as e:
        logger.error(f"Failed to clear checkpoints for chat_id {chat_id}: {e}")
        await update.message.reply_text("⚠️ An error occurred while clearing your conversation history.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming messages through the LangGraph agent."""
    chat_id = update.effective_chat.id
    user_text = update.message.text
    
    if not user_text:
        return
        
    logger.info(f"Received message from chat_id {chat_id}: '{user_text}'")
    
    # Show typing status to let the user know the agent is thinking/acting
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Configure LangGraph to store this conversation thread using the telegram chat_id
    graph_config = {"configurable": {"thread_id": str(chat_id)}}
    
    try:
        # Run agent graph with user message as input
        # Graph updates state by appending the new user message
        result = await graph.ainvoke(
            {"messages": [("user", user_text)]}, 
            config=graph_config
        )
        
        # Extract the last message (which is the final assistant response)
        final_message = result["messages"][-1]
        response_text = final_message.content
        
        # Extract plain text if the content is returned as a list of content blocks
        if isinstance(response_text, list):
            text_parts = []
            for block in response_text:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            response_text = "".join(text_parts)
            
        # Send reply back to the user
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error handling message for chat_id {chat_id}: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Sorry, I encountered an error while processing your request.")

async def post_shutdown(application):
    """Closes connections, specifically the SQLite checkpointer connection."""
    logger.info("Shutdown hook triggered. Closing checkpointer database.")
    try:
        if checkpointer:
            await checkpointer.__aexit__(None, None, None)
            logger.info("Checkpointer closed successfully.")
    except Exception as e:
        logger.error(f"Error closing checkpointer: {e}")

def main():
    """Initializes and runs the Telegram bot."""
    # Ensure config validation has completed
    logger.info("Starting Telegram Bot application...")
    
    # Build bot application
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    logger.info("Telegram Bot is polling. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
