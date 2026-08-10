"""Unit tests for NexusClient using mocked HTTP responses."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.nexus_client import NexusClient, NexusError

API = "https://nexus.test/service/rest/v1"


@pytest.fixture
def client(instance):
    return NexusClient(instance, timeout=5.0)


@respx.mock
async def test_list_repositories(client):
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "maven-central",
                    "format": "maven2",
                    "type": "proxy",
                    "url": "https://nexus.test/repository/maven-central",
                    "attributes": {"online": True},
                }
            ],
        )
    )
    repos = await client.list_repositories()
    assert len(repos) == 1
    assert repos[0].name == "maven-central"
    assert repos[0].format == "maven2"
    assert repos[0].online is True


@respx.mock
async def test_delete_repository_ok(client):
    route = respx.delete(f"{API}/repositories/my-repo").mock(
        return_value=httpx.Response(204)
    )
    await client.delete_repository("my-repo")
    assert route.called


@respx.mock
async def test_error_status_raises_with_code(client):
    respx.get(f"{API}/repositories").mock(return_value=httpx.Response(403, text="nope"))
    with pytest.raises(NexusError) as exc:
        await client.list_repositories()
    assert exc.value.status_code == 403


@respx.mock
async def test_connection_error_has_no_status(client):
    respx.get(f"{API}/repositories").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(NexusError) as exc:
        await client.list_repositories()
    assert exc.value.status_code is None


async def test_malformed_base_url_becomes_nexus_error(instance):
    # A stray quote in base_url (a common instances.yaml typo) must not crash
    # the whole dashboard; it should surface as a handled NexusError.
    instance.base_url = 'https://nexus.test:8081"'
    bad_client = NexusClient(instance, timeout=5.0)
    with pytest.raises(NexusError) as exc:
        await bad_client.list_repositories()
    # Handled as a connection-level NexusError (status_code None), not a raw
    # crash. httpx surfaces the malformed URL differently across versions
    # (InvalidURL on 0.28 vs ConnectError on 0.22), so assert the handled shape
    # rather than the exact message.
    assert exc.value.status_code is None


@respx.mock
async def test_list_components_pagination(client):
    respx.get(f"{API}/components").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "abc",
                        "repository": "maven-central",
                        "group": "org.foo",
                        "name": "bar",
                        "version": "1.0",
                        "format": "maven2",
                    }
                ],
                "continuationToken": "next-token",
            },
        )
    )
    page = await client.list_components("maven-central")
    assert page.items[0].id == "abc"
    assert page.continuation_token == "next-token"


@respx.mock
async def test_ping_collects_checks(client):
    respx.get(f"{API}/status").mock(return_value=httpx.Response(200))
    respx.get(f"{API}/status/check").mock(
        return_value=httpx.Response(
            200,
            json={
                "Available CPUs": {"healthy": True},
                "Blob Stores": {"healthy": False},
            },
        )
    )
    result = await client.ping()
    assert result["checks"] == {"Available CPUs": True, "Blob Stores": False}
    assert result["response_ms"] >= 0


@respx.mock
async def test_list_blobstores(client):
    respx.get(f"{API}/blobstores").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "default",
                    "type": "File",
                    "totalSizeInBytes": 1024,
                    "availableSpaceInBytes": 2048,
                    "blobCount": 7,
                }
            ],
        )
    )
    stores = await client.list_blobstores()
    assert stores[0].name == "default"
    assert stores[0].total_size_bytes == 1024
    assert stores[0].blob_count == 7


@respx.mock
async def test_non_json_200_becomes_nexus_error(client):
    """리버스프록시/SSO가 200+HTML을 주면 JSONDecodeError가 아니라 NexusError로
    정규화돼, 호출부의 except NexusError가 잡고 엔드포인트가 500되지 않아야 한다."""
    respx.get(f"{API}/blobstores").mock(
        return_value=httpx.Response(200, text="<html>login</html>",
                                    headers={"content-type": "text/html"}))
    with pytest.raises(NexusError):
        await client.list_blobstores()


@respx.mock
async def test_ping_non_dict_status_check(client):
    """/status/check가 dict가 아닌 JSON을 주어도 AttributeError로 터지지 않는다."""
    respx.get(f"{API}/status").mock(return_value=httpx.Response(200))
    respx.get(f"{API}/status/check").mock(return_value=httpx.Response(200, json=["oops"]))
    out = await client.ping()   # must not raise
    assert out["checks"] == {}


@respx.mock
async def test_cleanup_policies_fallback_to_beta(client):
    # v1 path returns 404 -> client should retry against beta namespace.
    respx.get(f"{API}/cleanup-policies").mock(return_value=httpx.Response(404))
    respx.get("https://nexus.test/service/rest/beta/cleanup-policies").mock(
        return_value=httpx.Response(
            200,
            json=[{"name": "old", "format": "maven2", "criteria": {"lastBlobUpdated": 30}}],
        )
    )
    policies = await client.list_cleanup_policies()
    assert policies[0].name == "old"
    assert policies[0].criteria == {"lastBlobUpdated": 30}
