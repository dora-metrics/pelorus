"""
A test runner to check grafana is functioning properly
"""

import unittest
import urllib3
import json
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

import openshift_login_page

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

    def _get_grafana_url(self):
        url = ""
        http = urllib3.HTTPSConnectionPool('kubernetes.default.svc.cluster.local', port=443, cert_reqs='CERT_NONE', assert_hostname=False)
        r = http.request('GET','/api') 
        print("Status: " + str(r.status))
        if r.status == 200:
            jsondata = json.loads(r.data)
            lburl = jsondata['serverAddressByClientCIDRs'][0]['serverAddress']
            url = lburl.replace('loadbalancer','grafana-proxy-pelorus.apps')
            url = url.replace(':443','')
            url = 'https://' + url 
        return url

    def test_case_grafana(self):
        """Find the prometheus targets and make sure they are up"""
        try:
            url = self._get_grafana_url()
            print(url)
            self.driver.get(url)

            loginPages = openshift_login_page.OpenshiftLoginPages(self.driver)
            loginPages.login_to_openshift()

            #print("Next page source:")
            #print(self.driver.page_source)

        except NoSuchElementException as ex:
            self.fail(ex.msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(GrafanaTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
