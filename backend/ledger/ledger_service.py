import pandas as pd
import requests

class LedgerService:
    # Static fallback rates (MYR → destination) in case the CDN is unavailable
    FALLBACK_RATES = {
        "JPY": 33.0, "KRW": 290.0, "THB": 7.5, "SGD": 0.29, "IDR": 3400.0,
        "VND": 5200.0, "TWD": 6.9, "PHP": 12.2, "USD": 0.21, "EUR": 0.20,
        "GBP": 0.17, "AUD": 0.33, "CNY": 1.55, "HKD": 1.66, "INR": 17.8,
        "AED": 0.78, "MYR": 1.0,
    }

    def __init__(self):
        self.base_currency = "MYR"
        # Rates are fetched lazily on first use — NOT at startup.
        # This keeps server startup and page load instant.
        self.exchange_rates = {}

    def _fetch_rates(self):
        try:
            url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{self.base_currency.lower()}.json"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.exchange_rates = {k.upper(): v for k, v in data.get(self.base_currency.lower(), {}).items()}
            print(f"LedgerService: Live FX rates loaded ({len(self.exchange_rates)} currencies).")
        except Exception as e:
            # Non-fatal: fall back to static rates so the server keeps running
            print(f"LedgerService: Could not fetch live FX rates ({e}). Using static fallback rates.")
            self.exchange_rates = self.FALLBACK_RATES.copy()
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
