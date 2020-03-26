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
        if child.get("xmlUrl")
    }
    print(feeds)

    Profiling(True)
    from pelican_planet.planet import Planet, logger


    logger.setLevel(10)

    p = Planet(feeds)
    p.get_feeds()

    assert len(p._articles) > 0
    #  print(p._articles)
