from .base_agent import BaseAgent

class TranslationAgent(BaseAgent):
    def translate(self, plan_data, target_lang="English"):
        system_prompt = f"""
        You are the Translation Agent for DaddiesTrip.
        Ensure all attraction names, food, and descriptions are clearly translated to {target_lang}.
        Maintain the structured JSON format.
        """
        return self.query(system_prompt, f"Data: {plan_data}")
