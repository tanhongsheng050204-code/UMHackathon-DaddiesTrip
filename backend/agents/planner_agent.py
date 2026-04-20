from .base_agent import BaseAgent

class PlannerAgent(BaseAgent):
    def plan(self, user_request):
        system_prompt = """
        You are the Planner Agent for DaddiesTrip.
        Your goal is to create a high-level logical itinerary based on the user's request.
        
        Focus on:
        - Logical route between attractions.
        - Morning/Afternoon/Evening schedule.
        - Food recommendations for each day.
        - Considering general weather patterns for the destination.
        
        Respond ONLY with a JSON object:
        {
            "participants": ["Adult 1", "Adult 2", "Adult 3", "Adult 4"],
            "itinerary": [
                {
                    "day": 1,
                    "location": "City",
                    "schedule": ["Morning: Activity", "Afternoon: Activity", "Evening: Activity"],
                    "food_recommendations": ["Dish/Restaurant 1", "Dish/Restaurant 2"],
                    "weather_advice": "Advice here"
                }
            ]
        }
        """
        return self.query(system_prompt, f"User Request: {user_request}")
