"""Authenticated inference client with a validated versioned response contract."""
import io
import httpx
from PIL import Image
from app.core.config import get_settings
from shared.contracts import AnalysisResult


class MLServiceClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.ML_SERVICE_URL

    async def analyze_image(self, image_bytes, vehicle_make='hyundai', vehicle_year=2022,
                            region='default', claim_id='', description='', registration_number=''):
        with Image.open(io.BytesIO(image_bytes)) as image:
            mime = Image.MIME[image.format]
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f'{self.base_url}/analyze',
                headers={'X-Service-Key': self.settings.ML_API_KEY},
                files={'file': ('image', image_bytes, mime)},
                data={'vehicle_make': vehicle_make, 'vehicle_year': str(vehicle_year),
                      'region': region, 'claim_id': claim_id, 'description': description,
                      'registration_number': registration_number},
            )
            response.raise_for_status()
            return AnalysisResult.model_validate(response.json()).model_dump()

    async def health_check(self):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f'{self.base_url}/ready')
                return response.json()
        except httpx.HTTPError:
            return {'status': 'unreachable'}


def get_ml_client():
    return MLServiceClient()
