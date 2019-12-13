import json

class OpenshiftLoginPages:
    def __init__(self,driver):
        """
        driver - the selenium driver
        """
        self.driver = driver

    def login_to_openshift(self):
        """
        Read login information and apply it to the openshift oauth proxy login pages
        """
        login = None
        with open("/login/login.json","r") as loginConfigFile:
            loginData = loginConfigFile.read()
            login = json.loads(loginData)
                
        loginButton = self.driver.find_element_by_class_name('btn-primary')
        loginButton.click()

        loginBox = self.driver.find_element_by_id('inputUsername')
        loginBox.send_keys(login['username'])

        loginPassBox = self.driver.find_element_by_id('inputPassword')
        loginPassBox.send_keys(login['password'])

        loginButton = self.driver.find_element_by_class_name('btn-primary')
        loginButton.click()

