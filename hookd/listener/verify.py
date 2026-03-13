import hmac
import hashlib
from collections import OrderedDict


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


class DeliveryTracker:
    def __init__(self, max_size: int = 10_000):
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max = max_size

    def check_and_record(self, delivery_id: str) -> bool:
        if delivery_id in self._seen:
            return False
        self._seen[delivery_id] = None
        if len(self._seen) > self._max:
            self._seen.popitem(last=False)
        return True
