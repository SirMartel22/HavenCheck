import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db import Base
from models import AreaPriceAverage, Hostel, UtilityReport
from tools.rent import check_rent_fairness
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

    def test_utility_math(self):
        result = check_utility_reliability(self.db, "h1")
        self.assertEqual(result["water_reliability_pct"], 50.0)
        self.assertEqual(result["electricity_issue_count"], 1)

    def test_scam_rules(self):
        result = flag_scam_risk("Pay a deposit now before viewing. Address later. Urgent, no ID.")
        self.assertEqual(result["risk_level"], "high")
        self.assertGreaterEqual(len(result["flags"]), 3)

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test", "AUTHORITY_EMAIL_TO": "authority@example.com"}, clear=False)
    @patch("tools.notify.resend.Emails.send", return_value={"id": "email-authority"})
    def test_authority_email(self, send):
        result = notify_hostel_authority("h1", "water", "No water")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["email_id"], "email-authority")
        self.assertEqual(send.call_args.args[0]["subject"], "Hostel Authority Alert: h1")

    @patch.dict("os.environ", {"RESEND_API_KEY": "re_test", "SECURITY_EMAIL_TO": "security@example.com"}, clear=False)
    @patch("tools.security.resend.Emails.send", side_effect=RuntimeError("API unavailable"))
    def test_security_email_failure_is_safe(self, _send):
        result = alert_community_security("h1", "Suspected scam", "Chat transcript")
        self.assertEqual(result["status"], "failed")
        self.assertIn("timestamp", result)


if __name__ == "__main__":
    unittest.main()
