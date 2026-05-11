import base64
import hashlib
import hmac
import json

from Crypto.Cipher import AES


class RedsysSignature:
    """
    Genera y valida firmas HMAC_SHA512_V1 para la integración
    con Redsys TPV Virtual (integración formulario/redirect).

    Uso:
        redsys = RedsysSignature(settings.REDSYS_SECRET_KEY)

        # Generar parámetros para el formulario de pago
        merchant_parameters, signature = redsys.generate_signature(params)

        # Validar firma del webhook de notificación
        is_valid = redsys.validate_notification(
            ds_merchant_parameters,
            ds_signature
        )
    """

    def __init__(self, secret_key: str):
        """
        secret_key: clave secreta obtenida del portal de administración
                    de Redsys (sección "Ver clave" en Consulta datos de Comercio)
        """
        self.secret_key = secret_key

    # ------------------------------------------------------------------
    # Métodos públicos
    # ------------------------------------------------------------------

    def generate_signature(self, params: dict) -> tuple[str, str]:
        """
        Genera Ds_MerchantParameters y Ds_Signature a partir del
        diccionario de parámetros del pago.

        Retorna:
            (Ds_MerchantParameters, Ds_Signature)
        """
        order = params.get("DS_MERCHANT_ORDER", "")

        merchant_parameters = self._encode_parameters(params)
        derived_key = self._derive_key(order)
        signature = self._compute_hmac(merchant_parameters, derived_key)

        return merchant_parameters, signature

    def validate_notification(
        self,
        ds_merchant_parameters: str,
        ds_signature: str,
    ) -> bool:
        """
        Valida la firma recibida en el webhook de notificación de Redsys.
        Debe llamarse siempre antes de procesar el resultado del pago.

        Retorna True si la firma es válida, False si la notificación
        debe ser rechazada.
        """
        try:
            decoded = self._decode_parameters(ds_merchant_parameters)
            order = decoded.get("Ds_Order", "")

            derived_key = self._derive_key(order)
            expected_signature = self._compute_hmac(ds_merchant_parameters, derived_key)

            return hmac.compare_digest(expected_signature, ds_signature)

        except Exception:
            return False

    def decode_parameters(self, ds_merchant_parameters: str) -> dict:
        """
        Decodifica Ds_MerchantParameters de Base64 y retorna el dict
        con los parámetros de la notificación (Ds_Response, Ds_Order, etc.)
        """
        return self._decode_parameters(ds_merchant_parameters)

    @staticmethod
    def is_payment_authorised(ds_response: str) -> bool:
        """
        Determina si el pago fue autorizado según el código Ds_Response
        de Redsys. Un pago es exitoso si Ds_Response está entre 0000 y 0099.
        """
        try:
            code = int(ds_response)
            return 0 <= code <= 99
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _derive_key(self, order: str) -> bytes:
        """
        Genera la clave derivada específica para una operación.

        Proceso según el manual de Redsys (HMAC SHA-512):
        1. Decodificar la clave secreta de Base64
        2. Recortar a 16 bytes (rellenar con ceros si es más corta)
        3. Cifrar el número de pedido con AES-128 CBC (IV = 16 bytes a cero)
        4. El resultado codificado en Base64 es la clave derivada
        """
        secret_decoded = base64.b64decode(self.secret_key)
        key = secret_decoded[:16].ljust(16, b'\0')
        iv = b'\0' * 16
        cipher = AES.new(key, AES.MODE_CBC, iv)

        order_bytes = order.encode('utf-8')
        padded_order = order_bytes.ljust(
            ((len(order_bytes) // 16) + 1) * 16,
            b'\0',
        )

        return cipher.encrypt(padded_order)

    def _compute_hmac(self, merchant_parameters: str, derived_key: bytes) -> str:
        """
        Calcula HMAC-SHA512 sobre Ds_MerchantParameters usando la clave
        derivada y retorna el resultado codificado en Base64 URL safe.
        """
        mac = hmac.new(
            derived_key,
            merchant_parameters.encode('utf-8'),
            hashlib.sha512,
        )
        return base64.urlsafe_b64encode(mac.digest()).decode('utf-8')

    @staticmethod
    def _encode_parameters(params: dict) -> str:
        """Serializa el dict a JSON y lo codifica en Base64."""
        json_str = json.dumps(params, separators=(',', ':'))
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    @staticmethod
    def _decode_parameters(ds_merchant_parameters: str) -> dict:
        """Decodifica Base64 y deserializa el JSON de parámetros."""
        decoded_bytes = base64.b64decode(ds_merchant_parameters)
        return json.loads(decoded_bytes.decode('utf-8'))


def build_payment_params(order) -> dict:
    from django.conf import settings

    redsys = RedsysSignature(settings.REDSYS_SECRET_KEY)

    params = {
        'DS_MERCHANT_AMOUNT': str(int(order.total * 100)),
        'DS_MERCHANT_ORDER': order.payment_provider_id,
        'DS_MERCHANT_MERCHANTCODE': settings.REDSYS_MERCHANT_CODE,
        'DS_MERCHANT_TERMINAL': settings.REDSYS_TERMINAL,
        'DS_MERCHANT_CURRENCY': '978',
        'DS_MERCHANT_TRANSACTIONTYPE': '0',
        'DS_MERCHANT_MERCHANTURL': settings.REDSYS_WEBHOOK_URL,
        'DS_MERCHANT_URLOK': settings.REDSYS_URL_OK,
        'DS_MERCHANT_URLKO': settings.REDSYS_URL_KO,
    }

    merchant_parameters, signature = redsys.generate_signature(params)

    redsys_url = (
        'https://sis-t.redsys.es:25443/sis/realizarPago'
        if getattr(settings, 'REDSYS_ENV', 'test') == 'test'
        else 'https://sis.redsys.es/sis/realizarPago'
    )

    return {
        'redsys_url': redsys_url,
        'Ds_MerchantParameters': merchant_parameters,
        'Ds_Signature': signature,
        'Ds_SignatureVersion': 'HMAC_SHA512_V1',
    }


def process_webhook(merchant_params_b64: str) -> None:
    from apps.orders.models import Order
    from apps.orders.services import confirm_order_payment, cancel_order

    redsys = RedsysSignature.__new__(RedsysSignature)
    params = redsys._decode_parameters(merchant_params_b64)

    order_ref = params.get('Ds_Order', '')
    ds_response = params.get('Ds_Response', '9999')

    try:
        order = Order.objects.get(payment_provider_id=order_ref)
    except Order.DoesNotExist:
        return

    if order.state in (Order.State.PAID, Order.State.CANCELLED):
        return

    if RedsysSignature.is_payment_authorised(ds_response):
        confirm_order_payment(order)
    else:
        cancel_order(order)
