class GrafanaHomePage:
    def __init__(self,driver):
        """
        driver - the selenium driver
        """
        self.driver = driver

    def click_home_dropdown(self):
        """
        Click the home button to search for dashboards
        """
        homeButtonDownArrow = self.driver.find_element_by_class_name('navbar-page-btn__search')
        homeButton = homeButtonDownArrow.find_element_by_xpath('..')
        homeButton.click()


    def click_on_dashboard(self,dashboard_name):
        """
        Find a dashboard name in the dropdown and click on it.
        """
        titles = self.driver.find_elements_by_class_name('search-item__body-title')
        specific_dashboard_titles = list(filter( lambda t: t.text == dashboard_name , titles))
        specific_dashboard_title = specific_dashboard_titles[0]

        dashboard_link = specific_dashboard_title.find_element_by_xpath('..')
        dashboard_link.click()

        
