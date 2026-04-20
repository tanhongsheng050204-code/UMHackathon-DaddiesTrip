from .base_agent import BaseAgent

class BudgetAgent(BaseAgent):
    def optimize(self, detailed_plan, budget_limit_myr):
        system_prompt = """
        You are the Budget Agent for DaddiesTrip.
        Review the detailed plan and calculate the ACTUAL total cost by summing:
        - Flights (cost_myr)
        - Every day's Hotel (cost_myr)
        - Every day's Food (daily_food_cost_myr)
        - Every day's Transport (cost_myr)
        - Every single Activity (cost_myr)
        
        Multiply daily costs by the number of days.
        Ensure estimated_total_cost_myr is the SUM of these actual costs, NOT just the user's budget limit.
        Determine if the budget_limit_myr is sufficient.
        
        Respond ONLY with a JSON object:
        {
            "estimated_total_cost_myr": 5420,
            "budget_recommendation": {
                "is_sufficient": true,
                "message": "Your actual cost is RM5420. Based on your RM6000 limit, you have RM580 remaining."
            },
            "saving_tips": ["Tip 1", "Tip 2"]
        }
        """
        user_prompt = f"Plan: {detailed_plan}\nBudget Limit: RM{budget_limit_myr}"
        return self.query(system_prompt, user_prompt)
