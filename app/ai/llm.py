from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.core.config import settings
from app.ai.prompts import customer_support_prompt
from app.ai.tools import get_order_status, search_support_documents, get_my_orders, get_my_order, cancel_my_order, place_customer_order, search_products

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
)

tools = [get_order_status, search_support_documents, search_products, place_customer_order, get_my_order, get_my_orders, cancel_my_order]
llm_with_tools = llm.bind_tools(tools)

tool_map = {
    "get_order_status": get_order_status,
    "search_support_documents": search_support_documents,
    "search_products" : search_products,
    "place_customer_order" : place_customer_order,
    "get_my_order" : get_my_order,
    "get_my_orders" : get_my_orders,
    "cancel_my_order" : cancel_my_order,
}

def generate_response(messages):

    langchain_messages = []
    for message in messages:
        if message["role"] == "user":
            langchain_messages.append(
                HumanMessage(content=message["content"])
            )

        elif message["role"] == "assistant":
            langchain_messages.append(
                AIMessage(content=message["content"])
            )
    
    prompt_messages = customer_support_prompt.invoke({
        "messages": langchain_messages
    })
    
    response =  llm_with_tools.invoke(prompt_messages)
    
    if response.tool_calls:
        langchain_messages.append(response)
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            tool = tool_map[tool_name]
            
            result = tool.invoke(tool_args)
            
            langchain_messages.append(
                ToolMessage(
                    content= result,
                    tool_call_id = tool_call["id"]
                )
            )
        
        final_response = llm_with_tools.invoke(
            langchain_messages
        )
        
        return final_response.content

    # response = llm.invoke(prompt_messages

    return response.content