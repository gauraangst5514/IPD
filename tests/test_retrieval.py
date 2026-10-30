import io, unittest
import numpy as np
from PIL import Image
from ml.retrieval.engine import RetrievalEngine
class RetrievalTests(unittest.TestCase):
    def test_texture_copy_has_geometric_support(self):
        rng=np.random.default_rng(17)
        image=Image.fromarray(rng.integers(0,256,(240,320,3),dtype=np.uint8))
        result=RetrievalEngine('unused').verify(image,image.copy())
        self.assertGreater(result['inliers'],10)
        self.assertEqual(result['method'],'SIFT_RANSAC')
    def test_blank_is_inconclusive(self):
        image=Image.new('RGB',(100,100),'white')
        result=RetrievalEngine('unused').verify(image,image)
        self.assertEqual(result['inliers'],0)
        self.assertEqual(result['status'],'insufficient_features')
    def test_search_ranks_embeddings_without_fraud_probability(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            path=Path(directory)/'a.jpg';Image.new('RGB',(100,100),'red').save(path)
            engine=RetrievalEngine(directory);engine.model=True;engine.records=[path]
            engine.vectors=np.array([[1.,0.]]);engine.encode=lambda im:np.array([1.,0.])
            buf=io.BytesIO();Image.new('RGB',(100,100),'red').save(buf,format='PNG')
            result=engine.search(buf.getvalue())
            self.assertEqual(result['candidates'][0]['image_id'],'a.jpg')
            self.assertFalse(result['physical_damage_identity_validated'])
            self.assertEqual(result['score_type'],'similarity_not_probability')

    def test_dynamic_add_image_and_stats(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            engine=RetrievalEngine(directory)
            engine.model=True
            engine.records=[]
            engine.vectors=None
            engine.encode=lambda im: np.array([0.5, 0.5])

            buf=io.BytesIO()
            Image.new('RGB',(100,100),'blue').save(buf,format='JPEG')
            data=buf.getvalue()

            res=engine.add_image(data, identifier='custom_blue.jpg')
            self.assertTrue(res['added'])
            self.assertEqual(res['gallery_size'], 1)
            self.assertEqual(len(engine.records), 1)
            self.assertEqual(engine.vectors.shape, (1, 2))

            # Adding duplicate should return added=False
            res_dup=engine.add_image(data, identifier='dup.jpg')
            self.assertFalse(res_dup['added'])
            self.assertEqual(res_dup['reason'], 'duplicate_image')
            self.assertEqual(res_dup['gallery_size'], 1)

            # Stats check
            stats=engine.stats()
            self.assertEqual(stats['gallery_size'], 1)
            self.assertTrue(stats['model_loaded'])

    def test_ingestion_survives_restart_and_preserves_filename_collisions(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            engine=RetrievalEngine(directory);engine.model=True
            engine.encode=lambda im: np.array([1., 0.])
            for color in ('red', 'blue'):
                buf=io.BytesIO();Image.new('RGB',(20,20),color).save(buf,format='PNG')
                result=engine.add_image(buf.getvalue(), '../../same-name.exe')
                self.assertTrue(result['added'])
                self.assertEqual(Path(result['image_id']).suffix, '.png')
            self.assertEqual(len(set(engine.records)), 2)
            restarted=RetrievalEngine(directory);restarted.model=True
            restarted.encode=engine.encode
            restarted._load_gallery()
            self.assertEqual(restarted.stats()['gallery_size'], 2)
            duplicate=restarted.add_image(buf.getvalue(), 'different-name')
            self.assertFalse(duplicate['added'])
            self.assertEqual(restarted.vectors.shape, (2, 2))

    def test_failed_embedding_leaves_gallery_unchanged_and_can_retry(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            engine=RetrievalEngine(directory);engine.model=True
            def fail(image):
                raise RuntimeError('encoder unavailable')
            engine.encode=fail
            buf=io.BytesIO();Image.new('RGB',(20,20),'red').save(buf,format='PNG')
            with self.assertRaises(RuntimeError):
                engine.add_image(buf.getvalue(), 'photo')
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(engine.seen_hashes, set())
            self.assertEqual(engine.records, [])
            self.assertIsNone(engine.vectors)
            engine.encode=lambda im: np.array([1., 0.])
            self.assertTrue(engine.add_image(buf.getvalue(), 'photo')['added'])

    def test_unsupported_image_rejected_before_loading_models(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            engine=RetrievalEngine(directory)
            buf=io.BytesIO();Image.new('RGB',(20,20)).save(buf,format='BMP')
            with self.assertRaises(ValueError):
                engine.add_image(buf.getvalue())
            self.assertIsNone(engine.model)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_lightglue_honors_matching_resolution_without_internal_upscale(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        class Extractor:
            def extract(self, tensor, **kwargs):
                self.shape=tuple(tensor.shape)
                self.resize=kwargs.get('resize', 'default')
                return {'features': 'test'}
        engine=RetrievalEngine('unused');engine.matcher=object();engine.extractor=Extractor()
        with patch.dict('sys.modules', {'lightglue': SimpleNamespace(SuperPoint=object, LightGlue=object)}):
            with patch.dict('os.environ', {'RETRIEVAL_EDGE':'640'}):
                _, size=engine.extract_lightglue(Image.new('RGB',(1280,800)))
        self.assertEqual(size, [640,400])
        self.assertEqual(engine.extractor.shape, (3,400,640))
        self.assertIsNone(engine.extractor.resize)

    def test_upload_validation_ignores_third_party_pillow_monkey_patch(self):
        import asyncio
        from fastapi import HTTPException, UploadFile
        from unittest.mock import patch
        from ml.serve import read_image
        from ml.image_input import open_upload
        with patch('PIL.Image.open', side_effect=RuntimeError('third-party auto-install')):
            for fmt in ('JPEG', 'PNG', 'WEBP'):
                stream=io.BytesIO();Image.new('RGB',(20,20),'blue').save(stream,format=fmt)
                content=stream.getvalue()
                with open_upload(content) as image:
                    self.assertEqual(image.size, (20,20))
                self.assertEqual(asyncio.run(read_image(UploadFile(io.BytesIO(content)))), content)
            for content in (b'invalid', b'\x89PNG\r\n\x1a\ninvalid'):
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(read_image(UploadFile(io.BytesIO(content))))
                self.assertEqual(context.exception.status_code, 422)
