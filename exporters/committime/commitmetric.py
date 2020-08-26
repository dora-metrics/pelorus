class CommitMetric():
    def __init__(self, app_name, _gitapi):
        self.name = app_name
        self.labels = None
        self.repo_url = None
        self.repo_protocol = None
        self.repo_fqdn = None
        self.repo_group = None
        self.repo_project = None
        self.commiter = None
        self.commit_hash = None
        self.commit_time = None
        self.commit_timestamp = None
        self.build_name = None
        self.build_config_name = None
        self.image_location = None
        self.image_name = None
        self.image_tag = None
        self.image_hash = None

    def parse_repourl(self):
        """Parses the repo_url into individual pieces"""
        if self.repo_url is None:
            return

        url_tokens = self.repo_url.split("/")
        self.repo_protocol = url_tokens[0]
        if self.repo_protocol.endswith(':'):
            self.repo_protocol = self.repo_protocol[:-1]
        # token 1 is always a blank
        self.repo_fqdn = url_tokens[2]
        self.repo_group = url_tokens[3]
        self.repo_project = url_tokens[4]

    def repo_combine_protocol_fqdn(self):
        """Returns the protocol and FQDN"""
        return str(self.repo_protocol + '://' + self.repo_fqdn)

    def repo_strip_git_from_project(self):
        """Returns the protocol and FQDN"""
        if self.repo_project.endswith('.git'):
            return self.repo_project[:-4]
        else:
            return self.repo_project
