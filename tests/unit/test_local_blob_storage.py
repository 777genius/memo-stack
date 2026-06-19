import asyncio

from infinity_context_adapters.local_blob import LocalBlobStorage


def test_local_blob_storage_lists_objects_with_prefix_and_cursor(tmp_path) -> None:
    async def run() -> None:
        storage = LocalBlobStorage(root_dir=tmp_path)
        await storage.write_bytes(storage_key="space/scope/a.txt", content=b"a")
        await storage.write_bytes(storage_key="space/scope/b.txt", content=b"bb")
        await storage.write_bytes(storage_key="space/other/c.txt", content=b"ccc")

        first_page = await storage.list_objects(prefix="space/scope", limit=1)
        second_page = await storage.list_objects(
            prefix="space/scope",
            limit=10,
            cursor=first_page.next_cursor,
        )

        assert [item.storage_key for item in first_page.objects] == ["space/scope/a.txt"]
        assert first_page.objects[0].byte_size == 1
        assert first_page.objects[0].updated_at is not None
        assert first_page.next_cursor == "space/scope/a.txt"
        assert [item.storage_key for item in second_page.objects] == ["space/scope/b.txt"]
        assert second_page.next_cursor is None

    asyncio.run(run())
