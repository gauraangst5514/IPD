"""Public S3 signing must not expose the container-only MinIO hostname."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

class S3SigningTests(unittest.TestCase):
    def test_public_endpoint_is_used_only_for_browser_urls(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
        from app.services.storage import StorageService
        with TemporaryDirectory() as directory:
            settings=SimpleNamespace(STORAGE_BACKEND="s3",UPLOADS_DIR=directory,
                S3_ENDPOINT="http://minio:9000",S3_PUBLIC_ENDPOINT="http://localhost:9000",
                S3_ACCESS_KEY="test",S3_SECRET_KEY="test-only",S3_BUCKET="test-bucket")
            internal=MagicMock();public=MagicMock()
            public.generate_presigned_url.return_value="http://localhost:9000/test-bucket/claim"
            with patch("app.services.storage.settings",settings),patch(
                    "app.services.storage.boto3.client",side_effect=[internal,public]) as factory:
                service=StorageService()
                url=service.get_presigned_url("claim")
                self.assertTrue(url.startswith("http://localhost:9000"))
                internal.head_bucket.assert_called_once()
                internal.generate_presigned_url.assert_not_called()
                public.generate_presigned_url.assert_called_once()
                self.assertEqual(factory.call_args_list[0].kwargs["endpoint_url"],"http://minio:9000")
                self.assertEqual(factory.call_args_list[1].kwargs["endpoint_url"],"http://localhost:9000")

if __name__=="__main__":unittest.main()
