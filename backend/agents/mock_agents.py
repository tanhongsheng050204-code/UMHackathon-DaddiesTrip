import json
import re
import time
from .planner_agent import PlannerAgent
from .booking_agent import BookingAgent
from .edge_agent import EdgeAgent
from .analyzer_agent import AnalyzerAgent
from .base_agent import AgentAPIError


class OrchestratorAgent:
    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.planner = PlannerAgent()
        self.booking = BookingAgent()
        self.edge = EdgeAgent()

    # ─── Context Compression Helpers ────────────────────────────────────────────

    @staticmethod
    def _build_trip_summary(prompt, itinerary_draft):
        """Compact dict (~50 tokens) to replace full prompt in downstream agents."""
        itinerary = itinerary_draft.get("itinerary", [])
        destination = itinerary[0].get("location", "Unknown") if itinerary else "Unknown"

        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        num_pax = int(num_match.group(1)) if num_match else len(itinerary_draft.get("participants", [])) or 1

        # Budget parsing — support "RM20k", "budget is 20k", "20000 budget", "budget of RM 5,000"
        budget_myr = 5000  # default
        budget_patterns = [
            r'RM\s*([\d,]+(?:\.\d+)?)\s*k\b',           # RM20k, RM 20k
            r'RM\s*([\d,]+(?:\.\d+)?)',                   # RM20000, RM 5,000
            r'budget\s+(?:is|of|around|about|:)?\s*(?:RM\s*)?([\d,]+(?:\.\d+)?)\s*k\b',  # budget is 20k
            r'budget\s+(?:is|of|around|about|:)?\s*(?:RM\s*)?([\d,]+(?:\.\d+)?)',          # budget is 20000
            r'([\d,]+)\s*k?\s*(?:budget|ringgit|myr)',    # 20k budget, 20000 myr
        ]
        for pat in budget_patterns:
            m = re.search(pat, prompt, re.IGNORECASE)
            if m:
                val = m.group(1).replace(',', '')
                try:
                    budget_myr = float(val)
                    # Check if the match was for a 'k' pattern
                    if 'k' in pat or (m.end() < len(prompt) and prompt[m.end():m.end()+1].lower() == 'k'):
                        budget_myr = budget_myr * 1000
                    elif budget_myr < 100:
                        # e.g. "budget is 20" likely means 20k
                        budget_myr = budget_myr * 1000
                    budget_myr = int(budget_myr)
                except ValueError:
                    budget_myr = 5000
                break

        # Extract travel dates/month from prompt
        travel_date_str = ""
        months = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)'
        date_match = re.search(r'(?:in|during|depart(?:ing)?(?:\s+in)?|around|for)\s+(' + months + r'(?:\s+\d{4})?)', prompt, re.IGNORECASE)
        if date_match:
            travel_date_str = date_match.group(1).strip()
        else:
            date_match2 = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', prompt)
            if date_match2:
                travel_date_str = date_match2.group(1)
            else:
                rel_match = re.search(r'(next\s+(?:week|month)|this\s+(?:month|' + months + r'))', prompt, re.IGNORECASE)
                if rel_match:
                    travel_date_str = rel_match.group(1)

        # Extract trip duration from prompt
        dur_match = re.search(r'(\d+)\s*[-–]?\s*days?', prompt, re.IGNORECASE)
        duration = int(dur_match.group(1)) if dur_match else len(itinerary)

        return {
            "destination": destination,
            "duration_days": duration,
            "participants": num_pax,
            "budget_myr": budget_myr,
            "depart_from": "KUL",
            "requires_flight": itinerary_draft.get("requires_flight", True),
            "travel_dates": travel_date_str,
        }

    @staticmethod
    def _compress_for_booking(itinerary_draft):
        """Strip non-essential planner fields before sending to BookingAgent."""
        return {
            "requires_flight": itinerary_draft.get("requires_flight", True),
            "itinerary": [
                {
                    "day": d.get("day"),
                    "location": d.get("location"),
                    "activities": [
                        {
                            "name": a.get("name"),
                            "schedule": a.get("schedule"),
                            "transport_to_next": a.get("transport_to_next")
                        }
                        for a in d.get("activities", [])
                    ],
                }
                for d in itinerary_draft.get("itinerary", [])
            ],
        }

    @staticmethod
    def _compress_for_budget(merged_itinerary, flight_options, num_participants, budget_limit_myr):
        """Send only cost fields to BudgetAgent — strips URLs, reviews, etc."""
        return {
            "num_participants": num_participants,
            "budget_limit_myr": budget_limit_myr,
            "flight_options": [
                {"airline": f.get("airline"), "cost_myr": f.get("cost_myr", 0)}
                for f in flight_options
            ],
            "days": [
                {
                    "day": d.get("day"),
                    "hotel_cost_myr": (d.get("hotel") or {}).get("cost_myr", 0),
                    "daily_food_cost_myr": d.get("daily_food_cost_myr", 0),
                    "transport_cost_myr": (d.get("transportation") or {}).get("cost_myr", 0) + sum(
                        (a.get("transport_to_next") or {}).get("estimated_cost_myr", 0)
                        for a in d.get("activities", [])
                    ),
                    "activity_costs_myr": [a.get("cost_myr", 0) for a in d.get("activities", [])],
                }
                for d in merged_itinerary
            ],
        }

    @staticmethod
    def _calculate_budget(merged_itinerary, flight_options, num_participants, budget_limit_myr):
        """Pure Python budget calculation — no LLM needed."""
        cheapest = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}
        flight_pp = cheapest.get("cost_myr", 0)
        day_pp = sum(
            (d.get("hotel") or {}).get("cost_myr", 0)
            + d.get("daily_food_cost_myr", 0)
            + (d.get("transportation") or {}).get("cost_myr", 0)
            + sum(
                a.get("cost_myr", 0) + (a.get("transport_to_next") or {}).get("estimated_cost_myr", 0)
                for a in d.get("activities", [])
            )
            for d in merged_itinerary
        )
        total = round((flight_pp + day_pp) * num_participants)
        surplus = budget_limit_myr - total
        is_ok = surplus >= 0
        tips = (
            [
                "Book flights 3–4 weeks ahead for better rates.",
                "Eat at local hawker stalls to save RM30–60/day per person.",
                "Choose a 3-star hotel to cut accommodation costs by ~40%.",
            ]
            if not is_ok else
            [
                "You have budget headroom — consider travel insurance for peace of mind.",
                "Pre-book popular attractions online to avoid queue surcharges.",
            ]
        )
        return {
            "estimated_total_cost_myr": total,
            "budget_recommendation": {
                "is_sufficient": is_ok,
                "message": (
                    f"Group total: RM{total:,} ({num_participants} pax). "
                    f"Budget: RM{budget_limit_myr:,} → "
                    f"{'Surplus' if is_ok else 'Deficit'} RM{abs(surplus):,}."
                ),
            },
            "saving_tips": tips,
        }

    # ─── Deep Merge Helper ──────────────────────────────────────────────────────

    @staticmethod
    def _merge_itineraries(raw_itinerary, raw_details):
        details_by_day = {d.get("day"): d for d in raw_details if d.get("day") is not None}
        merged = []
        for idx, day in enumerate(raw_itinerary):
            if not day.get("day"):
                day["day"] = idx + 1
            if not day.get("location"):
                day["location"] = "Destination"

            detail = details_by_day.get(day["day"]) or (raw_details[idx] if idx < len(raw_details) else {})
            booking_acts = detail.get("activities")
            if booking_acts:
                planner_by_name = {a.get("name", ""): a for a in day.get("activities", [])}
                day["activities"] = [
                    {**planner_by_name.get(b.get("name", ""), {}), **b}
                    for b in booking_acts
                ]
            for key, val in detail.items():
                if key != "activities":
                    day[key] = val
            merged.append(day)
        return merged

    # ─── Main Stream ────────────────────────────────────────────────────────────

    def process_prompt_stream(self, prompt: str):
        # Truncate runaway prompts
        words = prompt.split()
        if len(words) > 1500:
            prompt = " ".join(words[:1500])

        # ── Step 1: Analyzer (serial — must validate before anything else) ──────
        yield {"type": "progress", "text": "Validating your request..."}
        t0 = time.time()
        try:
            analyze_res = self.analyzer.analyze(prompt) or {}
        except AgentAPIError as e:
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Analyzer failed: {e}"}
            return
        print(f"Analyzer: {time.time() - t0:.1f}s")

        if analyze_res.get("status") == "invalid":
            yield {
                "type": "clarification",
                "message": analyze_res.get("message", "Please provide more details about your trip."),
                "missing_fields": analyze_res.get("missing_fields", []),
            }
            return

        # ── Step 2: Planner (serial — Booking needs its output) ──────────────────
        yield {"type": "progress", "text": "Planning your itinerary route..."}
        t1 = time.time()
        try:
            itinerary_draft = self.planner.plan(prompt) or {"itinerary": []}
        except AgentAPIError as e:
            yield {"type": "error", "message": e.user_message}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Planner failed: {e}"}
            return
        print(f"Planner: {time.time() - t1:.1f}s")

        # Participants
        participants_raw = itinerary_draft.get("participants", [])
        num_match = re.search(r'(\d+)\s*(?:adult|person|people|pax)', prompt, re.IGNORECASE)
        if num_match:
            participants_raw = [f"Adult {i+1}" for i in range(int(num_match.group(1)))]
        elif not participants_raw:
            participants_raw = ["User"]
        num_participants = len(participants_raw)

        trip_summary = self._build_trip_summary(prompt, itinerary_draft)
        budget_limit_myr = trip_summary["budget_myr"]

        # ── Stream partial itinerary skeleton immediately ─────────────────────────
        partial_days = [
            {
                "day": d.get("day") or (i + 1),
                "location": d.get("location") or "Destination",
                "activities": d.get("activities", []),
            }
            for i, d in enumerate(itinerary_draft.get("itinerary", []))
        ]
        yield {"type": "partial_itinerary", "days": partial_days, "num_participants": num_participants}

        # ── Step 3: Sequential execution ─────────────────────────────────────────
        yield {"type": "progress", "text": "Searching flights, hotels & activities..."}

        compressed_draft = self._compress_for_booking(itinerary_draft)
        booking_result = {}
        booking_error = None

        t2 = time.time()
        try:
            booking_result = self.booking.get_details(compressed_draft, trip_summary) or {}
        except AgentAPIError as e:
            booking_error = e.user_message
        except Exception as e:
            booking_error = f"Booking failed: {e}"
            print(f"Booking Agent error: {e}")
        print(f"Booking: {time.time() - t2:.1f}s")

        if booking_error:
            print(f"Booking Agent error (graceful fallback): {booking_error}")
            # Don't kill the whole trip — continue with planner-only data
            booking_result = {}

        # ── Stream partial flights immediately after booking ──────────────────────
        flight_options = booking_result.get("flight_options", [])
        if flight_options:
            yield {
                "type": "partial_flights",
                "flight_options": flight_options,
                "num_participants": num_participants,
            }

        yield {"type": "progress", "text": "Finalising costs and merging results..."}

        # ── Merge planner + booking ───────────────────────────────────────────────
        merged_itinerary = self._merge_itineraries(
            itinerary_draft.get("itinerary", []),
            booking_result.get("itinerary_details", []),
        )

        cheapest_flight = min(flight_options, key=lambda f: f.get("cost_myr", 9999)) if flight_options else {}

        # ── Step 3b: Python-side Budget (instant, no LLM) ────────────────────────
        budget_result = self._calculate_budget(
            merged_itinerary, flight_options, num_participants, budget_limit_myr
        )
        final_total = budget_result["estimated_total_cost_myr"]

        # ── Build split object for frontend ledger ────────────────────────────────
        dest_currency = booking_result.get("destination_currency", "MYR")
        # Rough MYR-to-destination conversion rates
        fx_rates = {
            "JPY": 33.0, "KRW": 290.0, "THB": 7.5, "SGD": 0.29, "IDR": 3400.0,
            "VND": 5200.0, "TWD": 6.9, "PHP": 12.2, "USD": 0.21, "EUR": 0.20,
            "GBP": 0.17, "AUD": 0.33, "CNY": 1.55, "HKD": 1.66, "INR": 17.8,
            "AED": 0.78, "MYR": 1.0,
        }
        fx = fx_rates.get(dest_currency, 1.0)
        per_person_myr = round(final_total / max(num_participants, 1))
        per_person_local = round(per_person_myr * fx, 2)

        split = {
            "primary_currency": "MYR",
            "destination_currency": dest_currency,
            "total_myr": final_total,
            "split_per_person_myr": per_person_myr,
            "split_per_person_local": per_person_local,
        }

        # ── Step 4: Edge Agent (Python-only, instant) ─────────────────────────────
        full_data = {
            "itinerary": merged_itinerary,
            "flight_options": flight_options,
            "flights": cheapest_flight,
            "num_participants": num_participants,
            "participants": participants_raw,
            "destination_currency": dest_currency,
            "destination_iata": booking_result.get("destination_iata", ""),
            "destination_review": booking_result.get("destination_review"),
            "estimated_total_cost_myr": final_total,
            "budget_recommendation": budget_result.get("budget_recommendation", {}),
            "budget_myr": budget_limit_myr,
            "saving_tips": budget_result.get("saving_tips", []),
            "split": split,
        }

        validated_data = self.edge.validate(full_data)
        yield {"type": "complete", "data": validated_data}

