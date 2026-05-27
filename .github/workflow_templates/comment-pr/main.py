import logging

from github import Auth, Github
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    input_token: SecretStr
    input_pr_number: int
    input_message: str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings()
        logging.info("Loaded settings: pr_number=%s", settings.input_pr_number)
        github_api = Github(auth=Auth.Token(settings.input_token.get_secret_value()))
        repo = github_api.get_repo("dora-metrics/pelorus")
        pull_request = repo.get_issue(number=settings.input_pr_number)
        pull_request.create_comment(settings.input_message)
    except Exception as error:
        logging.error("An error occurred: %s: %s", type(error).__name__, error)
        raise SystemExit(1)
    logging.info("Finished successfully")
