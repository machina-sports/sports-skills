def get_context(params):
    import json
    from sports_skills.news import fetch_items
    
    query = params.get("query", "NBA")
    limit = params.get("limit", 5)
    
    try:
        response = fetch_items(google_news=True, query=query, limit=limit)
        items = response.get("data", [])
        
        context_text = f"Here is the latest news about {query}:\n\n"
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            context_text += f"{i}. {title}\n"
            
        return {
            "context": context_text,
            "success": True
        }
    except Exception as e:
        return {
            "context": f"Failed to get news for {query}: {str(e)}",
            "success": False
        }
