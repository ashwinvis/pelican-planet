"""Profile and test performance"""
from xml.etree.ElementTree import parse
from pytest_profiling import Profiling


def test_perf(datadir):
    """Run as
    >>> pytest --profile-svg test_perf.py

    """
    Profiling(False)
    tree = parse("%s/feeds.opml" % datadir)
    feeds = {
        child.get("title"): child.get("xmlUrl")
        for child in tree.findall(".//outline")
    }
    print(feeds)

    Profiling(True)
    from pelican_planet.planet import Planet

    p = Planet(feeds)
    p.get_feeds()

