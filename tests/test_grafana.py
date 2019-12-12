"""
A test runner to check grafana is functioning properly
"""

import unittest
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

class GrafanaTests(unittest.TestCase):
    """Include test cases on a given url"""

    def setUp(self):
        """Start web driver"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def tearDown(self):
        """Stop web driver"""
        self.driver.quit()

    def test_case_grafana(self):
        """Find the prometheus targets and make sure they are up"""
        try:
            url = 'http://grafana-service:3000'
            self.driver.get(url)
        except NoSuchElementException as ex:
            self.fail(ex.msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(GrafanaTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
