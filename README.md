# MangaDex

`mangadex` is a synchronous Python client for the [MangaDex API](https://api.mangadex.org/docs/).

## Installation

Requires Python 3.11 or newer. Install from a local checkout:

```bash
python -m pip install .
```

Or install the current version directly from GitHub:

```bash
python -m pip install "mangadex @ git+https://github.com/princessmiku/MangaDexClient.git"
```

To use a specific Git tag, branch, or commit, append a revision after the repository URL:

```bash
python -m pip install "mangadex @ git+https://github.com/princessmiku/MangaDexClient.git@<revision>"
```

Replace `<revision>` with an existing tag, branch, or commit. Git must be installed
for installation from GitHub. Runtime dependencies (`httpx` and `tqdm`) are
installed automatically.

The distribution name is `mangadex`; the import is `from mangadex import MangaDexClient`.
The commands above install this repository directly and do not require a PyPI release.

## Usage

```python
from mangadex import MangaDexClient

with MangaDexClient() as client:
    results = client.manga.search("One Piece")
    for manga in results:
        print(manga.attributes.title.first)
```

The downloader is also available from the package root:

```python
from pathlib import Path

from mangadex import MangaDexClient, MangaDownloader

with MangaDexClient() as client:
    downloader = MangaDownloader(
        manga_id="your-manga-id",
        file_path=Path("downloads"),
        manga_dex_client=client,
    )
    downloader.download_complete_manga(language="en")
```

## Development

Install in editable mode so source changes take effect immediately:

```bash
python -m pip install -e .
```

Build distributable files locally:

```bash
python -m pip install build
python -m build
```

This creates a wheel and source distribution in `dist/`. Install the generated wheel with:

```bash
python -m pip install dist/mangadex-0.1.0-py3-none-any.whl
```

## Releases

The manual GitHub Actions workflow `Release` creates version commits, tags,
changelog entries, GitHub releases, and distribution artifacts automatically.
It runs only on the `master` branch.

Version numbers follow [Semantic Versioning](https://semver.org/) and are
determined from [Conventional Commits](https://www.conventionalcommits.org/):

- `fix: ...` creates a patch release, for example `0.1.0` to `0.1.1`.
- `feat: ...` creates a minor release, for example `0.1.0` to `0.2.0`.
- `feat!: ...` or a `BREAKING CHANGE:` footer creates a major release.

Commits without a release-relevant Conventional Commit type do not create a
new version.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
