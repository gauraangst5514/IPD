import unittest
from unittest.mock import patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

class PrivateMediaTests(unittest.TestCase):
    def setUp(self):
        import os
        self.environment=patch.dict(os.environ,{'DATABASE_URL':'sqlite+aiosqlite:///:memory:','SECRET_KEY':'media-test-only'})
        self.environment.start()
        from app.api.media import router
        from app.core.auth import create_access_token
        self.create_token=create_access_token
        app=FastAPI();app.include_router(router);self.client=TestClient(app)

    def tearDown(self):
        self.environment.stop()

    def test_signature_cannot_be_reused_for_another_image(self):
        token=self.create_token({'purpose':'private_image','key':'claims/a/photo.png'})
        with patch('app.api.media.get_storage_service') as storage:
            response=self.client.get('/media/claims/b/photo.png',params={'token':token})
            self.assertEqual(response.status_code,403);storage.assert_not_called()

    def test_login_token_does_not_grant_unscoped_photo_access(self):
        token=self.create_token({'sub':'test','role':'admin'})
        self.assertEqual(self.client.get('/media/claims/a/photo.png',params={'token':token}).status_code,403)

    def test_valid_photo_signature_serves_private_content(self):
        token=self.create_token({'purpose':'private_image','key':'claims/a/photo.png'})
        with patch('app.api.media.get_storage_service',return_value=Mock(download_image=Mock(return_value=b'image'))):
            response=self.client.get('/media/claims/a/photo.png',params={'token':token})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['cache-control'],'private, no-store')
