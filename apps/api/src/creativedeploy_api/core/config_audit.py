"""Safe command-line audit for the shared runtime configuration boundary."""

from sqlalchemy.engine import make_url

from creativedeploy_api.core.config import get_settings


def main() -> None:
    """Resolve Settings once and print only non-secret routing facts."""
    settings = get_settings()
    database_url = make_url(settings.require_database_url().get_secret_value())
    print(
        "Configuration consistent:"
        f" source={settings.database_configuration_source}"
        f" host={database_url.host}"
        f" port={database_url.port}"
        f" database={database_url.database}"
    )


if __name__ == "__main__":
    main()
