from .base_agent import BaseAgent

class EdgeAgent(BaseAgent):
    def validate(self, final_json):
        # 1. Python-side heuristic checks
        errors = []
        flights = final_json.get("flights", {})
        dep_air = flights.get("departure", {}).get("airport", "").upper()
        ret_air = flights.get("return", {}).get("airport", "").upper()
        
        if dep_air and ret_air and dep_air == ret_air:
            errors.append(f"Departure and Return airports are the same ({dep_air} to {ret_air}). This is impossible for a round trip. Fix the return flight to be FROM the destination.")
            
        all_act_costs = []
        for day in final_json.get("itinerary", []):
            for act in day.get("activities", []):
                cost = act.get("cost_myr", 0)
                if cost > 0:
                    all_act_costs.append(cost)
        
        if len(all_act_costs) >= 3 and len(set(all_act_costs)) == 1 and all_act_costs[0] == 25:
            errors.append("Every single attraction cost is exactly RM25. This is a hallucination. Please find actual diverse ticket prices or mark as Free.")
            
        if not errors:
            return final_json
            
        # 2. If errors, ask LLM to fix specifically
        print(f"Edge Agent detected errors: {errors}")
        system_prompt = f"""
        You are the Edge Case Handling Agent for DaddiesTrip.
        The current trip data has the following LOGICAL ERRORS:
        {". ".join(errors)}
        
        Fix the JSON and return the CORRECTED version. 
        - Ensure return airport is different from departure.
        - Ensure attraction costs are realistic and not all the same default value.
        """
        return self.query(system_prompt, f"JSON to Fix: {final_json}")
