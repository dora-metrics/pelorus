class GrafanaDashboardPage:
    def __init__(self,driver):
        """
        Take a selenium driver
        """
        self.driver = driver

    def has_panel(self,panel_name):
        """
        Find the panels with the names we want
        """
        panelTexts = self.driver.find_elements_by_class_name('panel-text-content')
        panelTextWeWant = list(filter(lambda p: p.text == panel_name , panelTexts ) )
        
        return len(panelTextWeWant) > 0
