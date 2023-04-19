import logging

from github import Github
from pydantic import BaseSettings, SecretStr


class Settings(BaseSettings):
    input_token: SecretStr
    pr_number: int
    input_message: str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings()
        logging.info(f"Loaded settings: {settings.json()}")
        github_api = Github(settings.input_token.get_secret_value())
        repo = github_api.get_repo("dora-metrics/pelorus")
        pull_request = repo.get_issue(number=settings.pr_number)
        pull_request.create_comment(settings.input_message)
    except Exception as error:
        logging.error(f"An error ocurred: {error}")
        raise SystemExit(1)
    logging.info("Finished successfully")
