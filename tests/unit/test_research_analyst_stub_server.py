from __future__ import annotations

import aiohttp
import pytest

from examples.research_analyst.app.stub_server import start_stub_server


@pytest.mark.asyncio
async def test_topic_a_returns_json():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/pages/topic-a") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "title" in data


@pytest.mark.asyncio
async def test_topic_b_returns_markdown():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/pages/topic-b") as resp:
                assert resp.status == 200
                body = await resp.text()
                assert body.startswith("#")


@pytest.mark.asyncio
async def test_flaky_fails_twice_then_succeeds():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as session:
            statuses = []
            for _ in range(3):
                async with session.get(f"{base_url}/pages/flaky") as resp:
                    statuses.append(resp.status)
            assert statuses == [503, 503, 200]


@pytest.mark.asyncio
async def test_counter_is_per_instance():
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/pages/flaky") as r:
                assert r.status == 503
    async with start_stub_server() as base_url:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/pages/flaky") as r:
                assert r.status == 503
