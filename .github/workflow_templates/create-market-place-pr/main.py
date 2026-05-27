import logging

from github import Auth, Github
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    input_token: SecretStr
    input_version: str
    input_fork_user: str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings()
        logging.info("Loaded settings: version=%s, fork_user=%s", settings.input_version, settings.input_fork_user)
        github_api = Github(auth=Auth.Token(settings.input_token.get_secret_value()))
        repo = github_api.get_repo(
            "redhat-openshift-ecosystem/community-operators-prod"
        )
        pull_request = repo.create_pull(
            title=f"operator pelorus-operator ({settings.input_version})",
            body=(
                f"## pelorus-operator files for version {settings.input_version}\n\n"
                "This pull request was created automatically after merging new version of "
                "[Pelorus](https://github.com/dora-metrics/pelorus)\n\n"
                # TODO read Owners file in repo root
                "Please review it\n- @etsauer\n- @KevinMGranger\n"
                "- @mpryc\n- @weshayutin\n\n"
                "After review, comment `/unhold` in This PR to merge it."
            ),
            base="main",
            head=f"{settings.input_fork_user}:pelorus-operator-{settings.input_version}",
            maintainer_can_modify=True,
        )
        pull_request.as_issue().create_comment("/hold")
    except Exception as error:
        logging.error("An error occurred: %s: %s", type(error).__name__, error)
        raise SystemExit(1)
    logging.info("Finished successfully")
