"""Rendered dashboard pages contain each panel exactly once (no duplicate IDs)."""

import unittest

import dashboard


class DashboardPagesTest(unittest.TestCase):
    def test_single_main_and_single_panels(self):
        for name, page in [('PAGE', dashboard.PAGE), ('STAFF_PAGE', dashboard.STAFF_PAGE)]:
            with self.subTest(page=name):
                self.assertEqual(page.count('</main>'), 1)
                self.assertEqual(page.count('id="voice-requests"'), 1)
                self.assertEqual(page.count('id="lunch-form"'), 1)

    def test_navigation_present(self):
        self.assertIn('aria-current="page">Medication log', dashboard.PAGE)
        self.assertIn('href="/staff"', dashboard.PAGE)
        self.assertIn('aria-current="page">Staff view', dashboard.STAFF_PAGE)
        self.assertIn('href="/"', dashboard.STAFF_PAGE)


if __name__ == '__main__':
    unittest.main()
