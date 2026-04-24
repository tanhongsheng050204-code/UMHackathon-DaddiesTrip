from .base_agent import BaseAgent
import datetime

class BookingAgent(BaseAgent):
    def get_details(self, compressed_draft, trip_summary):
        current_year = datetime.datetime.now().year
        today = datetime.date.today().isoformat()
        dest = trip_summary.get("destination", "the destination")
        requires_flight = trip_summary.get("requires_flight", True)
        travel_dates = trip_summary.get("travel_dates", "")
        duration = trip_summary.get("duration_days", 7)

        date_instruction = f"Travel dates: {travel_dates}." if travel_dates else f"Depart in {current_year}."

        system_prompt = f"""You are the Booking Agent for DaddiesTrip. Travellers depart from KUL, Malaysia.
Today is {today}. {date_instruction} All dates must be {current_year} or later. NEVER use past dates.

Return CONCISE JSON:
{{
  "destination_currency": "<ISO>",
  "destination_iata": "<IATA>",
  "destination_review": {{"name":"...","rating":"4.x/5","review_count":"...","review_comment":"short line"}},
  "flight_options": [/* 3 options if requires_flight, else [] */],
  "itinerary_details": [/* EXACTLY {duration} entries, one per day */]
}}

FLIGHTS (if requires_flight=true):
- Exactly 3 options with different airlines (e.g. AirAsia AK, Malaysia Airlines MH, Batik Air OD).
- "cost_myr"=per-person round-trip. departure.airport="KUL", return.airport=destination IATA.
- Include departure/return date, time, airline, airline_iata, cost_myr.

PER DAY — you MUST output EXACTLY {duration} days:
- "day": N
- "hotel": {{"name":"<real hotel name>","cost_myr":<number, NEVER 0>,"rating":"4.x/5"}}
  CRITICAL: EVERY single day MUST have a hotel with a realistic non-zero cost_myr. No exceptions.
  If consecutive days use the same hotel, repeat the hotel object anyway.
- "activities": [{{"name":"...","cost_myr":N,"schedule":"HH:MM-HH:MM"}}]
- "food_recommendations": EXACTLY 3 restaurants/food spots per day with REALISTIC costs:
  [{{"name":"<restaurant name>","avg_cost_myr":<number, NEVER 0>,"type":"breakfast|lunch|dinner"}}]
  Example: [{{"name":"Ichiran Ramen","avg_cost_myr":15,"type":"lunch"}},{{"name":"Sushi Dai","avg_cost_myr":25,"type":"dinner"}},{{"name":"7-Eleven Onigiri","avg_cost_myr":5,"type":"breakfast"}}]
- "daily_food_cost_myr": <sum of all food avg_cost_myr, NEVER 0>

43. BUDGET CONSTRAINT: The total group budget is RM {trip_summary.get('budget_myr', 5000)}. Select hotels and flights so the TOTAL group cost (all travellers) stays close to or under this limit. Prefer cost-effective options if the budget is tight.
44. Keep responses SHORT. Realistic costs for KUL→{dest}."""

        user_prompt = f"Trip: {trip_summary}\nItinerary to book: {compressed_draft}"
        return self.query(system_prompt, user_prompt, max_tokens=6000)
