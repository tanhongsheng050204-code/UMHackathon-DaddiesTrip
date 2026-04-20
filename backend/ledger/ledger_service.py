import pandas as pd
import requests

class LedgerService:
    def __init__(self):
        self.base_currency = "MYR"
        self.exchange_rates = {}
        self._fetch_rates()

    def _fetch_rates(self):
        try:
            # Free API requires no key
            response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{self.base_currency}", timeout=5)
            if response.status_code == 200:
                self.exchange_rates = response.json().get("rates", {})
        except requests.exceptions.RequestException:
            # Fallback mock rates if API is down
            self.exchange_rates = {
                "MYR": 1.0,
                "CNY": 1.52,
                "JPY": 32.0,
                "KRW": 286.0,
                "SGD": 0.28,
                "THB": 7.7,
                "USD": 0.21,
                "EUR": 0.19
            }

    def calculate_split(self, total_cost_myr: float, destination_currency: str, participants: list) -> dict:
        """
        Splits the expense equally among participants using Pandas for robust aggregation.
        """
        if not participants:
            return {}
            
        # Refresh rates if empty
        if not self.exchange_rates:
            self._fetch_rates()

        num_participants = len(participants)
        
        # Calculate local currency rate (Destination currency per 1 MYR)
        # E.g., if destination is CNY, rate might be ~1.52 (1 MYR = 1.52 CNY)
        rate = self.exchange_rates.get(destination_currency, 1.0)
        total_cost_local = total_cost_myr * rate

        # Create a dataframe to handle potential complex logic later
        df = pd.DataFrame({
            'Participant': participants,
            'Owed_MYR': [total_cost_myr / num_participants] * num_participants,
            'Owed_Local': [total_cost_local / num_participants] * num_participants
        })
        
        return {
            "primary_currency": "MYR",
            "destination_currency": destination_currency,
            "total_myr": total_cost_myr,
            "split_per_person_myr": round(df['Owed_MYR'].iloc[0], 2),
            "split_per_person_local": round(df['Owed_Local'].iloc[0], 2)
        }

    def settle_payment(self, user_id: str, card_number: str):
        # TC-02 (Negative Case): Invalid simulated payment card
        if card_number.startswith("0000"):
            return False, "Payment rejected: Invalid card number."
        return True, "Payment settled successfully."
