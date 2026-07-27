import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db import Base
from models import AreaPriceAverage, Hostel, UtilityReport
from tools.rent import check_rent_fairness
from tools.hostel import search_hostels
from tools.scam import flag_scam_risk
from tools.utility import check_utility_reliability
from tools.notify import notify_hostel_authority
from tools.security import alert_community_security


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(AreaPriceAverage(location="Tanke", avg_price_naira=150000, price_range_low=120000, price_range_high=180000))
        self.db.add(Hostel(id="h1", name="Test", location="Tanke", price_naira=150000, amenities=[], description="Test"))
        self.db.add_all([UtilityReport(hostel_id="h1", water_available=True, electricity_issue=False, comment="Good"), UtilityReport(hostel_id="h1", water_available=False, electricity_issue=True, comment="Outage")])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_rent_math(self):
        result = check_rent_fairness(self.db, "tanke", 195000)
        self.assertEqual(result["verdict"], "overpriced")
        self.assertEqual(result["difference_from_average_pct"], 30.0)

    def test_hostel_name_search_returns_complete_listing_details(self):
        result = search_hostels(self.db, "tes")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["matches"][0]["name"], "Test")
        self.assertEqual(result["matches"][0]["priceNaira"], 150000)
        self.assertEqual(result["matches"][0]["location"], "Tanke")

    def test_hostel_location_search_returns_matching_listings(self):
        result = search_hostels(self.db, location="tank")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["matches"][0]["name"], "Test")

    def test_utility_math(self):
        result = check_utility_reliability(self.db, "h1")
        self.assertEqual(result["water_reliability_pct"], 50.0)
        self.assertEqual(result["electricity_issue_count"], 1)

    def test_scam_rules(self):
        result = flag_scam_risk(self.db, "Pay a deposit now before viewing. Address later. Urgent, no ID.")
        self.assertEqual(result["risk_level"], "high")
        self.assertGreaterEqual(len(result["flags"]), 3)

    @patch.dict("os.environ", {"EMAIL_URL": "emailope.vercel.app", "AUTHORITY_EMAIL_TO": "authority@example.com"}, clear=False)
    @patch("httpx.post")
    def test_authority_email(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None
        result = notify_hostel_authority("h1", "water", "No water")
        self.assertEqual(result["status"], "sent")
        self.assertIsNotNone(result["email_id"])
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(called_args[0], "https://emailope.vercel.app")
        self.assertEqual(called_kwargs["json"]["to"], "authority@example.com")
        self.assertIn("Hostel Authority Alert: h1", called_kwargs["json"]["subject"])

    @patch.dict("os.environ", {"EMAIL_URL": "emailope.vercel.app", "SECURITY_EMAIL_TO": "security@example.com"}, clear=False)
    @patch("httpx.post", side_effect=Exception("API unavailable"))
    def test_security_email_failure_is_safe(self, mock_post):
        result = alert_community_security("h1", "Suspected scam", "Chat transcript")
        self.assertEqual(result["status"], "failed")
        self.assertIn("timestamp", result)


if __name__ == "__main__":
    unittest.main()
