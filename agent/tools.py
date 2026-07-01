import datetime
import ast
import operator
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from utils.logger import get_logger

logger = get_logger("agent.tools")

@tool
def get_current_datetime() -> str:
    """Get the current local date and time. Use this when the user asks about the current date, time, year, or day of the week."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# AST-based safe calculator implementation
operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

functions = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
}

def _eval_expr(node):
    if isinstance(node, ast.Num):  # Python <3.8 compatibility
        return node.n
    elif isinstance(node, ast.Constant):  # Python >=3.8
        return node.value
    elif isinstance(node, ast.BinOp):
        op = type(node.op)
        if op in operators:
            return operators[op](_eval_expr(node.left), _eval_expr(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = type(node.op)
        if op in operators:
            return operators[op](_eval_expr(node.operand))
    elif isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name in functions:
            args = [_eval_expr(arg) for arg in node.args]
            return functions[func_name](*args)
    raise TypeError(f"Unsupported mathematical syntax: {type(node)}")

@tool
def calculate_expression(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.
    Supported operations: addition (+), subtraction (-), multiplication (*), division (/), power (**),
    unary minus (-), absolute value (abs), rounding (round), min, max, sum.
    Example: expression="(5 + 3) * 12 / abs(-2)"
    """
    try:
        node = ast.parse(expression.strip(), mode="eval").body
        res = _eval_expr(node)
        return str(res)
    except Exception as e:
        logger.warning(f"Failed to calculate expression '{expression}': {e}")
        return f"Error evaluating expression '{expression}': {str(e)}"

@tool
async def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo to find up-to-date information on news, events, facts, etc.
    Returns search results as a text snippet.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=12.0) as client:
            # We try POST request first as it is less likely to trigger rate limits/captchas
            response = await client.post(url, data=params)
            
            if response.status_code != 200:
                logger.warning(f"DuckDuckGo POST returned status code {response.status_code}. Retrying with GET.")
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return f"Search failed with status code: {response.status_code}"
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            for body in soup.find_all("div", class_="result__body"):
                a_title = body.find("a", class_="result__a")
                snippet_div = body.find("a", class_="result__snippet")
                
                if a_title:
                    title = a_title.get_text(strip=True)
                    link = a_title.get("href")
                    
                    if link.startswith("//"):
                        link = "https:" + link
                    if "uddg=" in link:
                        try:
                            from urllib.parse import urlparse, parse_qs, unquote
                            parsed = urlparse(link)
                            qs = parse_qs(parsed.query)
                            if "uddg" in qs:
                                link = unquote(qs["uddg"][0])
                        except Exception:
                            pass
                            
                    snippet = snippet_div.get_text(strip=True) if snippet_div else ""
                    results.append(f"Title: {title}\nURL: {link}\nSnippet: {snippet}\n")
                    
            if not results:
                return "No search results found. The query might be too specific or search results were empty."
                
            return "\n---\n".join(results[:5])
            
    except Exception as e:
        logger.error(f"Error executing web search for query '{query}': {e}")
        return f"Error executing search: {str(e)}"
