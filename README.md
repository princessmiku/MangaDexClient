# MangaDex

`mangadex` is a synchronous Python client for the [MangaDex API](https://api.mangadex.org/docs/).

## Installation

Install a released version from PyPI:

```bash
pip install mangadex
```

Or install the current version directly from GitHub:

```bash
pip install "mangadex @ git+https://github.com/<YOUR-USERNAME>/MangaDex.git"
```

To use a specific Git tag, branch, or commit, append a revision after the repository URL:

```bash
pip install "mangadex @ git+https://github.com/<YOUR-USERNAME>/MangaDex.git@v0.1.0"
```

Replace `<YOUR-USERNAME>` with your GitHub account name after the repository has been pushed.

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

Build distributable files locally:

```bash
python -m build
```

This creates a wheel and source distribution in `dist/`. Install the generated wheel with:

```bash
pip install dist/mangadex-0.1.0-py3-none-any.whl
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
