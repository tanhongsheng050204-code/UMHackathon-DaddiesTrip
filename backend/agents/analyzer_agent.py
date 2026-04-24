from .base_agent import BaseAgent
import datetime

class AnalyzerAgent(BaseAgent):
    """
    AI-powered prompt analyzer.
    Identifies if any of the 4 required fields are missing:
    - Destination
    - Trip Dates (or month)
    - Participant count
    - Budget (in RM)
    """

    def analyze(self, user_request):
        """Validate the trip prompt using AI."""
        current_year = datetime.datetime.now().year
        
        system_prompt = f"""You are the Requirement Analyzer for DaddiesTrip.
Your job is to extract trip details and identify if ANY of the following are missing:
1. destination (e.g., Tokyo, Japan, Bali)
2. trip_dates (specific dates, a month like "June", or relative like "next week")
3. participants (number of people)
4. budget (an approximate amount in RM/MYR)

Current year is {current_year}.

If ALL 4 fields are present or can be reasonably inferred, return "status": "valid".
If ANY are missing, return "status": "invalid" and list the missing fields.

Output ONLY valid JSON in this format:
{{
  "status": "valid or invalid",
  "missing_fields": ["destination", "trip_dates", "participants", "budget"],
  "message": "A friendly message asking for the missing info, or empty if valid."
}}"""

        try:
            return self.query(system_prompt, f"User Request: {user_request}", max_tokens=300)
        except Exception as e:
            # Fallback to valid if AI fails, to allow the planner to try anyway
            print(f"Analyzer AI error: {e}")
            return {"status": "valid", "missing_fields": [], "message": ""}
