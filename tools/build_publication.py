"""Stage build validation inputs; publish the validated artifact bundle last."""
from pathlib import Path
import tempfile

from editor_storage import atomic_write_bytes


class BuildPublication:
    def __init__(self, temp_root):
        self.temp_root=Path(temp_root)
        self._temporary=None

    def __enter__(self):
        self.temp_root.mkdir(parents=True,exist_ok=True)
        self._temporary=tempfile.TemporaryDirectory(prefix='build-stage-',dir=self.temp_root)
        return self

    def path(self, name):
        if self._temporary is None or Path(name).name!=name:
            raise ValueError('build stage requires a simple filename and active context')
        return Path(self._temporary.name)/name

    def publish(self, artifacts):
        """Replace files only after validation; restore prior bytes on write failure.

        Receipts should be last in this sequence so readers cannot accept an
        incomplete bundle. Each replacement is atomic; this is not a filesystem
        transaction across paths. Previous bytes are held in memory, not .bak files.
        """
        files=[(Path(path),bytes(payload)) for path,payload in artifacts]
        paths=[path.resolve() for path,_ in files]
        if len(paths)!=len(set(paths)):
            raise ValueError('duplicate build publication destination')
        previous={path:path.read_bytes() if path.exists() else None for path,_ in files}
        written=[]
        try:
            for path,payload in files:
                written.append(path)
                # The replacement may succeed before directory fsync raises.
                # Include the attempted path so that case is rolled back too.
                atomic_write_bytes(path,payload)
        except BaseException:
            failed=[]
            for path in reversed(written):
                try:
                    if previous[path] is None:path.unlink(missing_ok=True)
                    else:atomic_write_bytes(path,previous[path])
                except OSError as error:failed.append(f'{path}: {error}')
            if failed:
                raise RuntimeError('Build publication rollback failed: '+'; '.join(failed))
            raise

    def __exit__(self, *_):
        self._temporary.cleanup()
        self._temporary=None
