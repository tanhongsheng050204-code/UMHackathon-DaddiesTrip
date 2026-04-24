from .base_agent import BaseAgent
import datetime

class PlannerAgent(BaseAgent):
    def plan(self, user_request):
        today = datetime.date.today().isoformat()
        current_year = datetime.datetime.now().year

        system_prompt = f"""You are the Planner Agent for DaddiesTrip. Create a high-level itinerary JSON. Today is {today}.

RULES:
- Output exactly N days if user asks for N days.
- Each day: "day" (int), "location" (string), "requires_flight" (bool).
- Activities: "name", "schedule" (e.g. 09:00-11:30), "cost_myr", "rating" (e.g. "4.5/5 Google Review").
- Transport: "transport_to_next": {{"mode":"walk or bus or metro or taxi","duration":"X min","estimated_cost_myr":0,"notes":"..."}}. Include line name for metro/train. Null for last activity. TRANSPORT ACCURACY: When describing airport transfers, you MUST use the correct airport. If you don't know which airport the flight uses, say "airport transfer" instead of naming a specific airport or train line.
- Include "participants" (array), "food_recommendations" (array per day, each with "name","avg_cost_myr","type","rating" e.g. "4.3/5"), "weather_advice" (string).
- Stay within user's budget. Prefer mid-range if budget is tight.
- All dates in {current_year} or later. Output ONLY valid JSON. 3-4 activities max per day.

JSON:
{{
  "requires_flight": true/false,
  "participants": ["Adult 1"],
  "itinerary": [{{"day":1,"location":"...","activities":[],"food_recommendations":[],"weather_advice":"..."}}]
}}"""
        return self.query(system_prompt, f"User Request: {user_request}", max_tokens=6000)
