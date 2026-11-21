import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from affil import norm_key, parse_affiliation  # noqa: E402


class AffiliationTests(unittest.TestCase):
    def check(self, aff, inst, country, dept):
        r = parse_affiliation(aff)
        self.assertIsNotNone(r, aff)
        self.assertEqual(r["institution"], inst, aff)
        self.assertEqual(r["country"], country, aff)
        self.assertEqual(r["dept"], dept, aff)

    def test_uc_campus(self):
        self.check("University of California, Berkeley, Department of EECS, CA, USA",
                   "University of California, Berkeley", "USA", "ee")

    def test_dept_after(self):
        self.check("Stanford University, Department of Electrical Engineering, CA, USA",
                   "Stanford University", "USA", "ee")

    def test_dept_before(self):
        self.check("School of Electrical Engineering, Tel Aviv University, Israel",
                   "Tel Aviv University", "Israel", "ee")

    def test_cs_dept(self):
        self.check("Carnegie Mellon University, Computer Science Department, Pittsburgh, PA, USA",
                   "Carnegie Mellon University", "USA", "other")

    def test_no_dept(self):
        self.check("Tsinghua University, Beijing, China", "Tsinghua University", "China", "unknown")

    def test_institute_of_technology(self):
        self.check("KTH Royal Institute of Technology, Stockholm, Sweden",
                   "KTH Royal Institute of Technology", "Sweden", "unknown")
        self.check("Georgia Institute of Technology, School of Electrical and Computer Engineering, Atlanta, GA, USA",
                   "Georgia Institute of Technology", "USA", "ee")

    def test_eth(self):
        self.check("ETH Zurich, Department of Information Technology and Electrical Engineering, Switzerland",
                   "ETH Zurich", "Switzerland", "ee")

    def test_college_of(self):
        self.check("Peking University, College of Engineering, Beijing, China",
                   "Peking University", "China", "unknown")

    def test_company_rejected(self):
        self.assertIsNone(parse_affiliation("Google Research, Mountain View, CA, USA"))
        self.assertIsNone(parse_affiliation("Microsoft Research Asia, Beijing, China"))
        self.assertIsNone(parse_affiliation("Chinese Academy of Sciences, Institute of Automation, Beijing, China"))

    def test_canada(self):
        self.check("University of Toronto, Department of Electrical and Computer Engineering, ON, Canada",
                   "University of Toronto", "Canada", "ee")

    def test_more_institutions(self):
        self.check("Korea Advanced Institute of Science and Technology, School of Electrical Engineering, Daejeon, Korea",
                   "Korea Advanced Institute of Science and Technology", "South Korea", "ee")
        self.check("TU Berlin, Deutschland", "TU Berlin", "Germany", "unknown")
        self.check("William & Mary, Williamsburg, VA, USA", "William & Mary", "USA", "unknown")

    def test_hospital_rejected(self):
        self.assertIsNone(parse_affiliation("Shengjing Hospital of China Medical University, Shenyang, China"))

    def test_other_dept_words(self):
        self.check("Xiamen University, College of the Environment and Ecology, China", "Xiamen University", "China", "other")

    def test_campus_with_acronym(self):
        self.check("University of California, Los Angeles (UCLA), Department of Electrical Engineering, CA, USA",
                   "University of California, Los Angeles", "USA", "ee")

    def test_ambiguous_system_rejected(self):
        self.assertIsNone(parse_affiliation("Beckman Laser Institute, University of California, CA, USA"))

    def test_hong_kong(self):
        self.check("The Chinese University of Hong Kong, Department of Electronic Engineering, Hong Kong, China",
                   "The Chinese University of Hong Kong", "Hong Kong", "ee")

    def test_acronym_stripped(self):
        self.check("Beijing University of Posts and Telecommunications (BUPT), Beijing, China",
                   "Beijing University of Posts and Telecommunications", "China", "unknown")
        self.assertEqual(norm_key("Chinese University of Hong Kong (Shenzhen)"),
                         "chinese university hong kong shenzhen")

    def test_country_inference(self):
        self.check("Pontificia Universidad Católica de Chile", "Pontificia Universidad Católica de Chile", "Chile", "unknown")
        self.check("Carnegie Mellon University Qatar", "Carnegie Mellon University Qatar", "Qatar", "unknown")
        self.check("University of Bahrain, Isa Town, Bahrain", "University of Bahrain", "Bahrain", "unknown")
        self.check("Universidad Nacional Autónoma de México, México", "Universidad Nacional Autónoma de México", "Mexico", "unknown")
        r = parse_affiliation("New Mexico State University, Las Cruces")
        self.assertNotEqual(r["country"], "Mexico")

    def test_norm_key(self):
        self.assertEqual(norm_key("University of Illinois at Urbana-Champaign"),
                         norm_key("University of Illinois Urbana-Champaign"))


if __name__ == "__main__":
    unittest.main()
