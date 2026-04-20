import json
import re
from .planner_agent import PlannerAgent
from .booking_agent import BookingAgent
from .budget_agent import BudgetAgent
from .edge_agent import EdgeAgent
from .translation_agent import TranslationAgent

class OrchestratorAgent:
    def __init__(self):
        self.planner = PlannerAgent()
        self.booking = BookingAgent()
        self.budget = BudgetAgent()
        self.edge = EdgeAgent()
        self.translator = TranslationAgent()

    def process_prompt(self, prompt: str) -> dict:
        # Step 1: Planner Agent
        print("Planner Agent working...")
        itinerary_draft = self.planner.plan(prompt) or {"itinerary": []}
        
        # Parse participant count from prompt (e.g. "4 adults")
        participants_raw = itinerary_draft.get("participants", [])
        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        if num_match:
            n = int(num_match.group(1))
            participants_raw = [f"Adult {i+1}" for i in range(n)]
        elif not participants_raw:
            participants_raw = ["User"]
        
        num_participants = len(participants_raw)
        
        # Step 2: Booking Agent
        print("Booking Agent working...")
        booking_details = self.booking.get_details(itinerary_draft, prompt) or {}
        
        # Merge booking details into itinerary safely
        merged_itinerary = []
        raw_itinerary = itinerary_draft.get("itinerary", [])
        raw_details = booking_details.get("itinerary_details", [])
        
        for i, day in enumerate(raw_itinerary):
            if i < len(raw_details):
                day.update(raw_details[i])
            merged_itinerary.append(day)
            
        # Step 3: Budget Agent
        print("Budget Agent working...")
        budget_match = re.search(r'RM\s*(\d+(?:,\d+)?k?|\d+)', prompt, re.IGNORECASE)
        budget_limit_str = budget_match.group(1).replace(',', '') if budget_match else "5000"
        if budget_limit_str.lower().endswith('k'):
            budget_limit_myr = int(budget_limit_str[:-1]) * 1000
        else:
            try:
                budget_limit_myr = int(budget_limit_str)
            except ValueError:
                budget_limit_myr = 5000
        
        # Use cheapest flight option for cost calculations
        flight_options = booking_details.get("flight_options", [])
        cheapest_flight = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}
        
        pre_budget_data = {
            "itinerary": merged_itinerary,
            "flight_options": flight_options,
            "flights": cheapest_flight,   # cheapest shown by default
            "destination_currency": booking_details.get("destination_currency", "CNY"),
            "destination_iata": booking_details.get("destination_iata", "")
        }
        
        # PYTHON SIDE: actual sum of costs PER PERSON then × num_participants
        cheapest_flight_cost_per_person = cheapest_flight.get("cost_myr", 0)
        day_costs_per_person = 0
        for day in merged_itinerary:
            day_costs_per_person += day.get("hotel", {}).get("cost_myr", 0)
            day_costs_per_person += day.get("daily_food_cost_myr", 0)
            day_costs_per_person += day.get("transportation", {}).get("cost_myr", 0)
            for act in day.get("activities", []):
                day_costs_per_person += act.get("cost_myr", 0)
        
        actual_total_all = (cheapest_flight_cost_per_person + day_costs_per_person) * num_participants
        
        budget_optimization = self.budget.optimize(pre_budget_data, budget_limit_myr) or {}
        
        llm_total = budget_optimization.get("estimated_total_cost_myr", 0)
        final_total = llm_total if isinstance(llm_total, (int, float)) and llm_total > 0 else actual_total_all
            
        full_data = {
            **pre_budget_data,
            "participants": participants_raw,
            "estimated_total_cost_myr": final_total,
            "budget_recommendation": budget_optimization.get("budget_recommendation", {}),
            "saving_tips": budget_optimization.get("saving_tips", [])
        }
        
        # Step 4: Edge Agent (Validation & Logic Check)
        print("Edge Agent working...")
        validated_data = self.edge.validate(full_data) or full_data
        
        # Step 5: Translation Agent
        print("Translation Agent working...")
        final_data = self.translator.translate(validated_data) or validated_data
        
        if "participants" not in final_data:
            final_data["participants"] = participants_raw
        if "flight_options" not in final_data:
            final_data["flight_options"] = flight_options
        
        return final_data
