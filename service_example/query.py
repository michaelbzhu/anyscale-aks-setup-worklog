import os
from urllib.parse import urljoin
import requests

# The "anyscale service deploy" script outputs a line that looks like
#
#     curl -H "Authorization: Bearer <SERVICE_TOKEN>" <BASE_URL>
#
# From this, you can parse out the service token and base URL.
token = "_e0Cr9XBQeCZcO56GwtxLD-S5kJ931vKi8Chpw-TF7w"  # Fill this in.
base_url = "https://my-first-service-8gzw9.cld-8nplnlihn9dyidul.s.anyscaleuserdata.com"  # Fill this in.

resp = requests.get(
    urljoin(base_url, "hello"),
    params={"name": "Theodore"},
    headers={"Authorization": f"Bearer {token}"},
)

print(resp.text)
