import base64
import hashlib
import hmac
import json

from Crypto.Cipher import DES3


class RedsysSignature:
    """
    Genera y valida firmas HMAC_SHA256_V1 para la integración
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
        try:
            from urllib.parse import unquote

            # 1. Limpiar la firma recibida
            ds_signature_clean = unquote(ds_signature).replace(' ', '+')

            # 2. Extraer el order para derivar la clave
            decoded = self._decode_parameters(ds_merchant_parameters)
            order = decoded.get("Ds_Order", "")

            print(f"[REDSYS] Order para derivar clave: '{order}'")

            # 3. Derivar clave y calcular firma esperada
            derived_key = self._derive_key(order)
            expected_signature = self._compute_hmac(ds_merchant_parameters, derived_key)

            print(f"[REDSYS] Firma esperada:  {expected_signature}")
            print(f"[REDSYS] Firma recibida:  {ds_signature_clean}")

            # 4. Comparar en ambos formatos (urlsafe y normal)
            expected_urlsafe = expected_signature  # ya es urlsafe en _compute_hmac
            expected_normal = expected_urlsafe.replace('-', '+').replace('_', '/')

            return (
                hmac.compare_digest(expected_urlsafe, ds_signature_clean)
                or hmac.compare_digest(expected_normal, ds_signature_clean)
            )

        except Exception as e:
            print(f"[REDSYS] Error en validación: {e}")
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

        Proceso según el manual de Redsys (HMAC SHA-256):
        1. Decodificar la clave secreta de Base64
        2. Cifrar el número de pedido con 3DES CBC (IV = 8 bytes a cero)
        3. El resultado es la clave derivada
        """
        secret_decoded = base64.b64decode(self.secret_key)
        iv = b'\0' * 8
        cipher = DES3.new(secret_decoded, DES3.MODE_CBC, iv)

        order_bytes = order.encode('utf-8')
        padded_order = order_bytes.ljust(
            ((len(order_bytes) + 7) // 8) * 8,
            b'\0',
        )

        return cipher.encrypt(padded_order)

    def _compute_hmac(self, merchant_parameters: str, derived_key: bytes) -> str:
        mac = hmac.new(
            derived_key,
            merchant_parameters.encode('utf-8'),
            hashlib.sha256,
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
    from apps.orders.services import _generate_payment_provider_id

    if not order.payment_provider_id:
        order.payment_provider_id = _generate_payment_provider_id()
        order.save(update_fields=['payment_provider_id'])

    redsys = RedsysSignature(settings.REDSYS_SECRET_KEY)

    params = {
        'DS_MERCHANT_AMOUNT': str(int(order.total * 100)),  # Importe en céntimos
        'DS_MERCHANT_ORDER': order.payment_provider_id,
        'DS_MERCHANT_MERCHANTCODE': settings.REDSYS_MERCHANT_CODE,
        'DS_MERCHANT_TERMINAL': settings.REDSYS_TERMINAL,
        'DS_MERCHANT_CURRENCY': '978',
        'DS_MERCHANT_TRANSACTIONTYPE': '0',
        'DS_MERCHANT_MERCHANTURL': settings.REDSYS_WEBHOOK_URL,
        'DS_MERCHANT_URLOK': settings.REDSYS_URL_OK,
        'DS_MERCHANT_URLKO': settings.REDSYS_URL_KO,
    }

    print("Payment params before signature:", params)

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
        'Ds_SignatureVersion': 'HMAC_SHA256_V1',
    }


def process_webhook(merchant_params_b64: str) -> None:
    from apps.orders.models import Order
    from apps.orders.services import confirm_order_payment, cancel_order

    # Use the proper instance, not __new__
    redsys = RedsysSignature.__new__(RedsysSignature)
    params = redsys._decode_parameters(merchant_params_b64)

    order_ref = params.get('Ds_Order', '')
    ds_response = params.get('Ds_Response', '9999')

    print(f"[REDSYS] Order ref: {order_ref}, Ds_Response: {ds_response}")

    try:
        order = Order.objects.get(payment_provider_id=order_ref)
    except Order.DoesNotExist:
        print(f"[REDSYS] Order not found for ref: {order_ref}")
        return

    if order.state in (Order.State.PAID, Order.State.CANCELLED):
        print(f"[REDSYS] Order {order.id} already in final state: {order.state}")
        return

    if RedsysSignature.is_payment_authorised(ds_response):
        print(f"[REDSYS] Payment authorised for order {order.id}")
        confirm_order_payment(order)
    else:
        print(f"[REDSYS] Payment denied for order {order.id}")
        cancel_order(order)