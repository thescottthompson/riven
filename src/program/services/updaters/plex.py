"""Plex Updater module"""

import time

from kink import di
from loguru import logger
from plexapi.exceptions import BadRequest, Unauthorized
from plexapi.library import LibrarySection
from requests.exceptions import ConnectionError as RequestsConnectionError
from urllib3.exceptions import MaxRetryError, NewConnectionError, RequestError

from program.apis.plex_api import PlexAPI
from program.services.updaters.base import BaseUpdater
from program.settings import settings_manager


class PlexUpdater(BaseUpdater):
    def __init__(self):
        super().__init__("plexupdater")
        self.library_path = settings_manager.settings.updaters.library_path
        self.settings = settings_manager.settings.updaters.plex
        self.api = None
        self.sections = dict[LibrarySection, list[str]]()
        self._initialize()

    def validate(self) -> bool:  # noqa: C901
        """Validate Plex library.

        Retries transient connection errors with exponential backoff so that
        Riven booting just before its Plex container is reachable doesn't
        permanently disable the updater for the lifetime of the process.
        Authentication / config errors fail fast — only network-level errors
        are retried.
        """

        if not self.settings.enabled:
            return False

        if not self.settings.token:
            logger.error("Plex token is not set!")
            return False

        if not self.settings.url:
            logger.error("Plex URL is not set!")
            return False

        if not self.library_path:
            logger.error("Library path is not set!")
            return False

        # Retry only transient network failures (e.g. Plex container not yet
        # reachable on container boot). Each retry roughly doubles the wait.
        max_attempts = 6
        delays = [2, 4, 8, 15, 30]

        for attempt in range(1, max_attempts + 1):
            try:
                self.api = di[PlexAPI]
                self.api.validate_server()
                self.sections = self.api.map_sections_with_paths()
                self.initialized = True

                if attempt > 1:
                    logger.info(
                        f"Plex validate succeeded on attempt {attempt}/{max_attempts}"
                    )

                return True
            except Unauthorized as e:
                logger.error(f"Plex is not authorized!: {e}")
                return False
            except BadRequest as e:
                logger.exception(f"Plex is not configured correctly!: {e}")
                return False
            except (
                TimeoutError,
                MaxRetryError,
                NewConnectionError,
                RequestsConnectionError,
                RequestError,
            ) as e:
                if attempt < max_attempts:
                    delay = delays[attempt - 1]
                    logger.warning(
                        f"Plex unreachable (attempt {attempt}/{max_attempts}): "
                        f"{type(e).__name__}: {e}. Retrying in {delay}s."
                    )
                    time.sleep(delay)
                    continue

                logger.exception(
                    f"Plex unreachable after {max_attempts} attempts: {e}"
                )
                return False
            except Exception as e:
                logger.exception(f"Plex exception thrown: {e}")
                return False

        return False

    def refresh_path(self, path: str) -> bool:
        """Refresh a specific path in Plex by finding the matching section"""

        assert self.api is not None, "Plex API is not initialized"

        for section, section_paths in self.sections.items():
            for section_path in section_paths:
                if path.startswith(section_path):
                    return self.api.update_section(section, path)

        return False
