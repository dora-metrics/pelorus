import logging

from github import Github
from pydantic import BaseSettings, SecretStr


class Settings(BaseSettings):
    input_token: SecretStr
    input_version: str
    input_fork: str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings()
        logging.info(f"Loaded settings: {settings.json()}")
        github_api = Github(settings.input_token.get_secret_value())
        repo = github_api.get_repo(
            "redhat-openshift-ecosystem/community-operators-prod"
        )
        pull_request = repo.create_pull(
            # TODO write better descriptions after tests
            title="Automation test - DELETE IT",
            body="This is an automation test, this PR will be closed without merging\n@mateusoliveira43 @mpryc",
            base="main",
            head=f"{settings.input_fork}:pelorus-operator-{settings.input_version}",
            maintainer_can_modify=True,
            # TODO remove draft?
            draft=True,
        )
        pull_request.add_to_labels("do-not-merge/hold ")
    except Exception as error:
        logging.error(f"An error ocurred: {error}")
        raise SystemExit(1)
    logging.info("Finished successfully")
