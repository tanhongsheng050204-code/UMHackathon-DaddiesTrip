import pytest
from unittest.mock import patch, MagicMock
from backend.agents.mock_agents import OrchestratorAgent
from backend.agents.base_agent import BaseAgent
from backend.ledger.ledger_service import LedgerService


@patch('backend.ledger.ledger_service.LedgerService._fetch_rates')
def test_tc01_happy_case(mock_fetch_rates):
    mock_analyze = {"status": "valid", "missing_fields": [], "message": ""}
    mock_plan = {
        "itinerary": [{
            "day": 1, "location": "Tokyo",
            "activities": [{"name": "Arrival", "cost_myr": 0, "source": "N/A"}],
            "hotel": {"name": "Hotel A", "cost_myr": 100},
            "daily_food_cost_myr": 50,
            "transportation": {"cost_myr": 20}
        }],
        "participants": ["Alice", "Bob"]
    }
    mock_booking = {
        "flight_options": [{"airline": "ANA", "cost_myr": 800}],
        "itinerary_details": [{
            "day": 1,
            "hotel": {"name": "Hotel A", "cost_myr": 100},
            "activities": [{"name": "Arrival", "cost_myr": 0, "schedule": "09:00"}]
        }]
    }

    # 1st call: Analyzer, 2nd: Planner, 3rd: Booking
    with patch.object(BaseAgent, 'query', side_effect=[mock_analyze, mock_plan, mock_booking]):
        agent = OrchestratorAgent()
        prompt = "Plan a trip to Tokyo in June for 2 people with a budget of RM 5000."

        events = []
        for event in agent.process_prompt_stream(prompt):
            events.append(event)

        complete_event = next((e for e in events if e["type"] == "complete"), None)
        assert complete_event is not None

        result = complete_event["data"]
        assert result["estimated_total_cost_myr"] > 0
        assert len(result["itinerary"]) == 1


def test_tc02_negative_case():
    ledger = LedgerService()
    success, message = ledger.settle_payment("user1", "0000-1234-5678-9012")
    assert not success
    assert "rejected" in message.lower()


def test_ai01_oversized_input():
    mock_analyze = {"status": "valid", "missing_fields": [], "message": ""}
    mock_plan = {"itinerary": []}

    with patch.object(BaseAgent, 'query', side_effect=[mock_analyze, mock_plan]) as mock_query:
        agent = OrchestratorAgent()
        oversized_prompt = ("word " * 1600) + " to Tokyo in June for 2 people with budget RM 5000"

        events = list(agent.process_prompt_stream(oversized_prompt))

        # The Planner call is mock_query call index 1
        planner_call = mock_query.call_args_list[1]
        user_message = planner_call[0][1]  # second positional arg = user_prompt
        # Agents may prefix the prompt (e.g. "User Request: "), so strip known prefixes
        stripped = user_message.replace("User Request: ", "")
        assert len(stripped.split()) <= 1500
