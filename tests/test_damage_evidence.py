import unittest
import numpy as np
from PIL import Image
from ml.retrieval.damage_evidence import DamageEvidence
class FakeEncoder:
 def encode(self,image):
  a=np.asarray(image)/255.;return np.array([a[:10,:10].mean(),a[10:,10:].mean()])
class EvidenceTests(unittest.TestCase):
 def tool(self):
  tool=DamageEvidence.__new__(DamageEvidence)
  tool.detector=type('Detector',(),{'trained':True})()
  tool.boxes=lambda im:[{'confidence':.9,'bbox':[0,0,10,10]}]
  return tool
 def test_scaled_correspondence_and_equal_area_control(self):
  image=Image.new('RGB',(20,20),'white'); image.paste('black',(0,0,10,10))
  result=self.tool().explain(FakeEncoder(),image,image,{'query_size':[10,10],'candidate_size':[10,10], 'correspondences':[{'query':[2,2],'candidate':[2,2]},{'query':[9,9],'candidate':[9,9]}]})
  self.assertEqual(result['damage_supported_correspondences'],1)
  self.assertTrue(result['background_control_available'])
  self.assertIsNotNone(result['damage_minus_background_drop'])
 def test_no_detection_does_not_invent_explanation(self):
  tool=self.tool();tool.boxes=lambda im:[]
  result=tool.explain(FakeEncoder(),Image.new('RGB',(20,20)),Image.new('RGB',(20,20)),{})
  self.assertFalse(result['available'])
 def test_detector_normalized_centre_boxes_become_pixel_corners(self):
  tool=DamageEvidence.__new__(DamageEvidence);tool.cache={}
  tool.detector=type('Detector',(),{'detect':lambda self,data:{'detections':[{'bbox':[.5,.5,.4,.2],'confidence':.8}]}})()
  box=tool.boxes(Image.new('RGB',(200,100)))[0]['bbox']
  np.testing.assert_allclose(box,[60,40,140,60])
