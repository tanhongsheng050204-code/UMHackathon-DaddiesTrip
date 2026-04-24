import pytest
from unittest.mock import patch, MagicMock
from backend.agents.mock_agents import OrchestratorAgent
from backend.ledger.ledger_service import LedgerService

# Mocking the streaming response for OpenAI client
class MockStream:
    def __init__(self, content):
        self.content = content
    def __iter__(self):
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = self.content
        return iter([chunk])

@patch('openai.resources.chat.completions.Completions.create')
@patch('backend.ledger.ledger_service.LedgerService._fetch_rates')
def test_tc01_happy_case(mock_fetch_rates, mock_create):
    mock_plan = '{"itinerary": [{"day": 1, "location": "Tokyo", "activities": [{"name":"Arrival", "cost_myr": 0, "source":"N/A"}], "hotel": {"name": "Hotel A", "cost_myr": 100}, "daily_food_cost_myr": 50, "transportation": {"cost_myr": 20}}], "participants": ["Alice", "Bob"]}'
    mock_booking = '{"flight_options": [{"airline": "ANA", "cost_myr": 800}], "itinerary_details": [{"day": 1, "hotel": {"name": "Hotel A", "cost_myr": 100}, "activities": [{"name":"Arrival", "cost_myr": 0, "schedule": "09:00"}]}]}'
    
    mock_create.side_effect = [
        MockStream(mock_plan),
        MockStream(mock_booking)
    ]
    
    agent = OrchestratorAgent()
    ledger = LedgerService()
    ledger.exchange_rates = {"USD": 0.25} 
    
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

@patch('openai.resources.chat.completions.Completions.create')
def test_ai01_oversized_input(mock_create):
    mock_create.return_value = MockStream('{"itinerary": []}')
    
    agent = OrchestratorAgent()
    # Prompt with more than 1500 words
    oversized_prompt = ("word " * 1600) + " to Tokyo in June for 2 people with budget RM 5000"
    
    # We just need to trigger the Planner call
    # The first event is "Validating...", second is "Planning..." (which calls LLM)
    gen = agent.process_prompt_stream(oversized_prompt)
    next(gen) # Validating...
    next(gen) # Planning...
    
    # Check the call to create
    assert mock_create.called
    kwargs = mock_create.call_args[1]
    user_message = kwargs['messages'][1]['content']
    assert len(user_message.split()) <= 1500
