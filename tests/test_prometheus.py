"""
A test runner to check pelorus is functioning properly
"""

import unittest
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

class PrometheusTests(unittest.TestCase):
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

    def test_case_prometheus_targets_up(self):
        """Find the prometheus targets and make sure they are up"""
        try:
            url = 'http://prometheus-pelorus:9090/targets'
            self.driver.get(url)
            element_list = self.driver.find_elements_by_class_name('state')
            
            if( len(element_list) < 1 ):
                self.fail("Couldn't find state element, no targets are up")

            states = set(map( lambda el: el.text, element_list ))
            
            self.assertTrue( "UP" in states ) #there should be at least one host up
            self.assertFalse( "DOWN" in states ) #there should not be any down hosts

        except NoSuchElementException as ex:
            self.fail(ex.msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(PrometheusTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
