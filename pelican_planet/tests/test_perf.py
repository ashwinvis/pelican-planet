"""Profile and test performance"""
import os
from pathlib import Path
from xml.etree.ElementTree import parse
from pytest_profiling import Profiling


def test_perf(datadir, tmpdir):
    """Run as::

        PYTHONASYNCIODEBUG=1 pytest --profile-svg --log-cli-level=10 test_perf.py

    """
    Profiling(False)
    tree = parse("%s/feeds.opml" % datadir)
    feeds = {
        child.get("title"): child.get("xmlUrl")
        for child in tree.findall(".//outline")
        if child.get("xmlUrl")
    }
    print(feeds)

    Profiling(True)
    from pelican_planet.planet import Planet, logger

    p = Planet(
        feeds,
        max_articles_per_feed=2,
        max_age_in_days=365,
        resolve_redirects=True,
    )
    p.get_feeds()

    templatepath = Path(datadir.join("planet.md.tmpl").strpath)
    destinationpath = Path(tmpdir.join("planet.md").strpath)
    p.write_page(templatepath, destinationpath)

    assert len(p._articles) > 0
    #  print(p._articles)
