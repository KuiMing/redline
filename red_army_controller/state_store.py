from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


class StateFileError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeatCredentials:
    game_id: str
    player_id: str
    resume_token: str
    role: str = "host"
    player_name: str = "紅軍 Agent"


class StateStore:
    def __init__(self, path: Path):
        self.path = path.expanduser()

    def save(self, credentials: SeatCredentials) -> None:
        if self.path.is_symlink():
            raise StateFileError(f"Refusing to write through symlink: {self.path}")
        parent = self.path.parent
        created_parent = not parent.exists()
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if created_parent:
            os.chmod(parent, 0o700)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(credentials), handle, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self) -> SeatCredentials:
        if not self.path.exists():
            raise StateFileError(f"State file not found: {self.path}")
        if self.path.is_symlink():
            raise StateFileError(f"Refusing to read symlink: {self.path}")
        mode = stat.S_IMODE(self.path.stat().st_mode)
        if mode & 0o077:
            raise StateFileError(f"State file permissions must be 0600: {self.path}")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return SeatCredentials(
                game_id=str(data["game_id"]),
                player_id=str(data["player_id"]),
                resume_token=str(data["resume_token"]),
                role=str(data.get("role") or "host"),
                player_name=str(data.get("player_name") or "紅軍 Agent"),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StateFileError(f"Invalid state file: {self.path}") from exc
