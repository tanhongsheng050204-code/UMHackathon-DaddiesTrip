from .base_agent import BaseAgent
import datetime

class PlannerAgent(BaseAgent):
    def plan(self, user_request):
        today = datetime.date.today().isoformat()
        current_year = datetime.datetime.now().year

        system_prompt = f"""You are the Planner Agent for DaddiesTrip.
Create a high-level itinerary JSON. Today is {today}.

CRITICAL RULES:
1. If the user asks for N days, you MUST output exactly N days. Do NOT output fewer.
2. Each day MUST have: "day" (int), "location" (string), "requires_flight" (bool).
3. Activities: "name", "schedule" (e.g. 09:00-11:30), "cost_myr".
4. Transport: "transport_to_next": {{"mode":"walk|bus|metro|taxi", "duration":"X min", "estimated_cost_myr":0, "notes":"..."}}. For metro/train: include the specific line name in notes (e.g. "JR Yamanote Line", "Tokyo Metro Ginza Line"). Null for last activity of day.
5. Include "participants" (array), "food_recommendations" (array per day), "weather_advice" (string).
13. STRICT BUDGET ADHERENCE: If the user provides a budget (e.g. RM 5000), you MUST select hotels and activities whose combined costs (for all participants) stay within that limit. Prefer mid-range or budget options if the total is tight.
14. All dates MUST be in {current_year} or later. Use the travel dates the user specified.
15. Output ONLY valid JSON. Keep each day concise (3-4 activities max).

JSON structure:
{{
  "requires_flight": true/false,
  "participants": ["Adult 1", ...],
  "itinerary": [
    {{
      "day": 1,
      "location": "...",
      "activities": [...],
      "food_recommendations": [...],
      "weather_advice": "..."
    }}
  ]
}}"""
        return self.query(system_prompt, f"User Request: {user_request}", max_tokens=6000)
