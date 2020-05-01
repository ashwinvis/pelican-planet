# Copyright (c) 2016 - Mathieu Bridon <bochecha@daitauha.fr>
#
# This file is part of pelican-planet
#
# pelican-planet is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pelican-planet is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pelican-planet.  If not, see <http://www.gnu.org/licenses/>.


import asyncio
import logging
from operator import attrgetter
from datetime import datetime, timedelta

import aiohttp
import async_timeout
import feedparser
from jinja2 import Template

from .utils import make_date, make_summary


logger = logging.getLogger("asyncio")


class FeedError(Exception):
    pass


class Planet:
    def __init__(
        self,
        feeds,
        max_articles_per_feed=None,
        max_summary_length=None,
        max_age_in_days=1e5,
        resolve_redirects=False,
    ):
        self._feeds = feeds
        self._max_articles_per_feed = max_articles_per_feed
        self._max_summary_length = max_summary_length
        self._max_age = datetime.now() - timedelta(days=max_age_in_days)
        self._resolve_redirects = resolve_redirects

        self._articles = []
        self._timeout = 15

    async def _fetch(self, url):
        logger.info(f"Fetching {url}")
        async with aiohttp.ClientSession() as session:
            with async_timeout.timeout(self._timeout):
                async with session.get(url) as response:
                    # NOTE: specifying encoding makes the fetching process at
                    # least 2x faster. It also avoids some errors and speeds up
                    # by avoiding guesses
                    # https://github.com/aio-libs/aiohttp/issues/3936
                    logger.info(f"Done fetching {url}")
                    return (
                        await response.text(encoding="utf-8"),
                        response.status,
                    )

    async def _get_feed(self, name, url):
        try:
            html, status = await self._fetch(url)
        except Exception as e:
            raise FeedError(
                "Could not parse %s's feed: %s. %s" % (name, url, e)
            )

        if status is None:
            raise FeedError("Could not download %s's feed: %s" % (name, html))

        elif status == 404:
            raise FeedError(
                "404: Could not download %s's feed: not found" % name
            )

        elif status not in (200, 301, 302):
            raise FeedError(
                "%d: Error with %s's feed: %s" % (status, name, html)
            )

        return html, name

    async def _get_feeds(self):
        tasks = []
        for name, url in self._feeds.items():
            task = asyncio.create_task(self._get_feed(name, url))
            tasks.append(task)

        # print("Waiting for all feeds")
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _get_articles(self, feed, feed_name):
        def _get_articles():
            for article in feed["entries"]:
                article["updated"] = make_date(article["updated"])
                article["summary"] = make_summary(
                    article["summary"], max_words=self._max_summary_length
                )
                article["feed_name"] = feed_name

                yield article

        articles = sorted(
            _get_articles(), key=attrgetter("updated"), reverse=True
        )
        articles = articles[: self._max_articles_per_feed]

        def latest(article):
            date = article["updated"].replace(tzinfo=None)
            return date > self._max_age

        articles = filter(latest, articles)

        return articles

    async def _resolve_redirect(self, url):
        """Resolves redirect urls.

        This is the async equivalent of:
        #  with urllib.request.urlopen(url) as f:
        #     return f.geturl()
        """
        async with aiohttp.ClientSession() as session:
            with async_timeout.timeout(self._timeout):
                async with session.get(url, allow_redirects=True) as response:
                    return str(response.url)

    async def _resolve_article_urls(self, articles):
        for article in articles:
            try:
                url = article["link"]
                try:
                    redirected_url = await self._resolve_redirect(url)
                except aiohttp.client_exceptions.ClientError as e:
                    raise asyncio.TimeoutError(str(e))

                if redirected_url != url:
                    logger.info(f"{article['link']} -> {redirected_url}")
                    article["link"] = redirected_url
            except asyncio.TimeoutError:
                logger.error(f"Redirect resolution timed out for {url}")
        return articles

    def get_feeds(self):
        results = asyncio.run(self._get_feeds())
        for result in results:
            # Unwrap results and check for exceptions
            if isinstance(result, FeedError):
                err = str(result)
                idx = min(500, len(err))
                logger.error(err[:idx])
                continue
            else:
                html, name = result
                logger.info("Successfully parsed {}'s feed".format(name))

            feed = feedparser.parse(html)
            articles = self._get_articles(feed, name)
            self._articles.extend(articles)

    def write_page(self, template, destination, max_articles=None):
        articles = sorted(
            self._articles, key=attrgetter("updated"), reverse=True
        )
        articles = articles[:max_articles]

        if self._resolve_redirects:
            articles = asyncio.run(self._resolve_article_urls(articles))

        with template.open() as fp:
            template = Template(fp.read())

        with destination.open(mode="w") as fp:
            fp.write(template.render(articles=articles))
