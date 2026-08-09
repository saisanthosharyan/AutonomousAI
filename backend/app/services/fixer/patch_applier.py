from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Dict

from app.core.logger import logger


class PatchApplier:
    """
    Applies validated patches safely.

    Features:
    - Automatic backup
    - Creates missing folders
    - Atomic write
    - Rollback on failure
    """

    def apply(
        self,
        project_path: str,
        patches: List[Dict[str, str]],
    ) -> dict:

        logger.info("=" * 60)
        logger.info("Patch Applier Started")
        logger.info("=" * 60)

        project = Path(project_path).resolve()

        backups = []

        modified = []

        try:

            for patch in patches:

                relative_path = Path(patch["path"])

                target = (project / relative_path).resolve()

                if project not in target.parents and target != project:
                    raise ValueError(
                        f"Illegal patch path: {relative_path}"
                    )

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                backup = None

                # ----------------------------
                # Backup existing file
                # ----------------------------

                if target.exists():

                    backup = target.with_suffix(
                        target.suffix + ".bak"
                    )

                    shutil.copy2(
                        target,
                        backup,
                    )

                    backups.append(
                        (
                            target,
                            backup,
                        )
                    )

                # ----------------------------
                # Write new file
                # ----------------------------

                temp_file = target.with_suffix(target.suffix + ".tmp")

                temp_file.write_text(
                    patch["content"],
                    encoding="utf-8",
                )

                temp_file.replace(target)

                modified.append(
                    str(relative_path)
                )

                logger.info(
                    "Updated %s",
                    relative_path,
                )

            # ----------------------------
            # Remove backups
            # ----------------------------

            for _, backup in backups:

                if backup.exists():

                    backup.unlink()

            logger.info(
                "Applied %d patch(es).",
                len(modified),
            )

            return {
                "success": True,
                "modified": modified,
            }

        except Exception as exc:

            logger.exception(
                "Patch application failed."
            )

            # ----------------------------
            # Rollback
            # ----------------------------
            for patch in patches:

                target = (project / patch["path"]).resolve()

                if target.exists() and not any(
                    target == original
                    for original, _ in backups
                ):

                    try:

                        target.unlink()

                    except Exception:

                        logger.exception(
                            "Failed to remove newly created file."
                        )
            for target, backup in backups:

                try:

                    if backup.exists():

                        shutil.copy2(
                            backup,
                            target,
                        )

                        backup.unlink()

                except Exception:

                    logger.exception(
                        "Rollback failed."
                    )

            return {
                "success": False,
                "modified": modified,
                "error": str(exc),
            }

        finally:

            logger.info("=" * 60)
            logger.info("Patch Applier Finished")
            logger.info("=" * 60)