import sys
sys.path.append(r'C:/Users/W1NDe/Documents/GitHub/M-AzurLaneAutoScript')
import requests
from module.log_res.log_res import logger
import base64,requests,cv2,datetime, hashlib, hmac, json
from urllib.parse import quote, urlencode


class BaiduOcr:
    def __init__(self,config,api_key=None,secret_key=None):
        self.name = "baidu"
        self.api_key = api_key or config.DropRecord_BaiduAPIKey
        self.secret_key = secret_key or config.DropRecord_BaiduAPISecret
        self.access_token = self._get_access_token(self.api_key, self.secret_key)
        
    def _get_access_token(self,client_id="xxxx", client_secret="yyyy"):
        """
        Get Baidu OCR API access token
        
        Returns:
            str: access_token
        """
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}"
        
        payload = ""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload)
        result = response.json()
        if 'access_token' in result:
            return result['access_token']
        else:
            logger.warning('Failed to get Baidu OCR access token')
            return None
        
    def request_ocr(self,image,model="general_basic"):
        # Convert image to base64
        _, buffer = cv2.imencode('.png', image)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Call Baidu OCR API
        request_url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/{model}"
        params = {"image": img_base64}
        access_token = self.access_token
        if not access_token:
            logger.warning('Failed to get access token, cannot request Baidu OCR API')
            return False
            
        request_url = request_url + "?access_token=" + access_token
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        response = requests.post(request_url, data=params, headers=headers)
        
        if response:
            result = response.json()
            return result
        else:
            logger.warning('Failed to call Baidu OCR API')
            return False
        
class VolcOcr:
    """
    Provides an interface to the Volcengine OCR (Optical Character Recognition) service.

    This class handles the V4 signing process required for authenticating requests
    to the Volcengine visual services API (cv).
    """
    def __init__(self, config, api_key=None, secret_key=None):
        """
        Initializes the VolcOcr client.

        :param config: A configuration object, expected to have DropRecord_VolcAPIKey and DropRecord_VolcAPISecret attributes.
        :param api_key: Your Volcengine Access Key ID. Overrides the value from the config.
        :param secret_key: Your Volcengine Secret Access Key. Overrides the value from the config.
        """
        self.name = "volc"
        # Credentials from config or direct parameters
        self.ak = api_key or getattr(config, 'DropRecord_VolcAPIKey', None)
        self.sk = secret_key or getattr(config, 'DropRecord_VolcAPISecret', None)
        
        # Static parameters for the Volcengine CV OCRNormal service
        self.service = "cv"
        self.version = "2020-08-26"
        self.region = "cn-north-1"
        self.host = "visual.volcengineapi.com"
        self.content_type = "application/x-www-form-urlencoded"
        self.action = "OCRNormal"
        self.method = "POST"

    # Volcengine signing helper functions
    @staticmethod
    def hmac_sha256(key: bytes, content: str):
        return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


    @staticmethod
    def hash_sha256(content: str):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


    @staticmethod
    def norm_query(params):
        query = ""
        for key in sorted(params.keys()):
            if type(params[key]) == list:
                for k in params[key]:
                    query = (
                            query + quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
                    )
            else:
                query = (query + quote(key, safe="-_.~") + "=" + quote(params[key], safe="-_.~") + "&")
        query = query[:-1]
        return query.replace("+", "%20")

    def request_ocr(self, image=None, image_url=None, image_base64=None,
                         approximate_pixel=None, mode=None, 
                         filter_thresh=None, half_to_full=None,model=None):
        if image is None and image_url is None and image_base64 is None:
            logger.error("Either 'image', 'image_url', or 'image_base64' must be provided for Volcengine OCR.")
            raise ValueError("Either 'image', 'image_url', or 'image_base64' must be provided.")

        body_params = {}
        if image_base64:
            body_params['image_base64'] = image_base64
        elif image is not None:
            if image_url:
                logger.warning("Both 'image' and 'image_url' provided. 'image' will be used.")
            
            # Per documentation, JPG format is recommended for better compatibility.
            success, buffer = cv2.imencode('.jpg', image)
            if not success:
                logger.error("Failed to encode image as JPEG.")
                return None
            img_base64_str = base64.b64encode(buffer).decode('utf-8')
            body_params['image_base64'] = img_base64_str
        elif image_url:
            body_params['image_url'] = image_url

        # Add optional parameters if they are provided, using snake_case as per API documentation.
        if approximate_pixel is not None:
            body_params['approximate_pixel'] = str(approximate_pixel)
        if mode is not None:
            body_params['mode'] = mode
        if filter_thresh is not None:
            body_params['filter_thresh'] = str(filter_thresh)
        if half_to_full is not None:
            body_params['half_to_full'] = str(half_to_full).lower()

        raw_response = self._signed_request(query={}, body_params=body_params)
        return self._format_response(raw_response)

    def _format_response(self, response):
        """
        Formats the raw Volcengine OCR response into a standardized structure.

        :param response: The raw JSON dictionary from the Volcengine API.
        :return: A dictionary with a single 'words_result' key, or the original
                 response if formatting fails or the response was an error.
        """
        if not response or 'data' not in response or not response.get('data'):
            logger.warning("Volcengine OCR response is invalid or contains no data; returning raw response.")
            return response

        try:
            words_result = []
            line_texts = response['data'].get('line_texts', [])
            # The 'line_rects' field contains the bounding box for each text line.
            # We assume it's a list of dictionaries, each with 'X', 'Y', 'Width', 'Height'.
            line_rects = response['data'].get('line_rects', [])

            if len(line_texts) != len(line_rects):
                logger.warning("Mismatch between number of text lines and bounding boxes in Volcengine response.")

            for text, rect in zip(line_texts, line_rects):
                location = {
                    'top': rect.get('y', 0),
                    'left': rect.get('x', 0),
                    'width': rect.get('width', 0),
                    'height': rect.get('height', 0)
                }
                words_result.append({
                    'words': text,
                    'location': location
                })
            
            return {'words_result': words_result}
        except (TypeError, KeyError) as e:
            logger.error(f"Failed to parse Volcengine OCR response data: {e}")
            return response # Return original response if parsing fails

    def _signed_request(self, query, body_params):
        """
        Orchestrates the signing and sending of a request to the Volcengine API.

        :param query: A dictionary of query parameters.
        :param body_params: A dictionary of body parameters (pre-urlencoding).
        :return: The JSON response from the API as a dictionary, or None on failure.
        """
        if not self.ak or not self.sk:
            logger.error("Volcengine OCR AK or SK not configured.")
            return None
        
        # The body must be url-encoded before signing.
        body = urlencode(body_params)

        request_param = {
            "body": body,
            "host": self.host,
            "path": "/",
            "method": self.method,
            "content_type": self.content_type,
            "date": datetime.datetime.utcnow(),
            "query": {"Action": self.action, "Version": self.version, **query},
        }
        
        try:
            # Generate all necessary headers, including the signature.
            headers = self._get_signed_headers(request_param)
            
            # Send the authenticated request.
            r = requests.request(
                method=self.method,
                url=f"https://{self.host}/",
                headers=headers,
                params=request_param["query"],
                data=body.encode("utf-8"),
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Volcengine failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error("--- VOLCENGINE ERROR RESPONSE ---")
                logger.error(f"STATUS CODE: {e.response.status_code}")
                try:
                    error_details = e.response.json()
                    logger.error(f"RESPONSE JSON:\n{json.dumps(error_details, indent=2)}")
                except json.JSONDecodeError:
                    logger.error(f"RESPONSE BODY:\n{e.response.text}")
                logger.error("--- END OF RESPONSE ---")
            return None
            
    def _get_signed_headers(self, request_param):
        """
        Calculates the V4 signature and returns the complete headers for the request.

        This function implements the four-step signature calculation process
        described in the Volcengine API documentation.

        :param request_param: A dictionary containing all request details.
        :return: A dictionary of headers ready to be sent.
        """
        # Step 1: Create a CanonicalRequest.
        # This is a standardized representation of the request.
        x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
        x_content_sha256 = self.hash_sha256(request_param["body"])
        signed_headers_str = ";".join(["content-type", "host", "x-content-sha256", "x-date"])

        canonical_request = "\n".join([
            request_param["method"].upper(),
            request_param["path"],
            self.norm_query(request_param["query"]),
            "\n".join([
                "content-type:" + request_param["content_type"],
                "host:" + request_param["host"],
                "x-content-sha256:" + x_content_sha256,
                "x-date:" + x_date,
            ]),
            "",
            signed_headers_str,
            x_content_sha256,
        ])
        
        # Step 2: Create the StringToSign.
        # This string combines metadata about the request and the hashed CanonicalRequest.
        short_x_date = x_date[:8]
        hashed_canonical_request = self.hash_sha256(canonical_request)
        credential_scope = f"{short_x_date}/{self.region}/{self.service}/request"
        string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])

        # Step 3: Calculate the Signature.
        # The signature is derived from a series of HMAC-SHA256 hashes.
        k_date = self.hmac_sha256(self.sk.encode("utf-8"), short_x_date)
        k_region = self.hmac_sha256(k_date, self.region)
        k_service = self.hmac_sha256(k_region, self.service)
        k_signing = self.hmac_sha256(k_service, "request")
        signature = self.hmac_sha256(k_signing, string_to_sign).hex()

        # Step 4: Assemble the Authorization header and other required headers.
        authorization = (
            f"HMAC-SHA256 Credential={self.ak}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, Signature={signature}"
        )
        
        headers = {
            "Authorization": authorization,
            "Content-Type": request_param["content_type"],
            "Host": request_param["host"],
            "X-Content-Sha256": x_content_sha256,
            "X-Date": x_date,
        }
        return headers


if __name__ == "__main__":
    volc_ocr = VolcOcr(None,"",
                  "==")
    baidu_ocr = BaiduOcr(None,"",
                  "")
    image_path = "C:/Users/W1NDe/Documents/GitHub/M-AzurLaneAutoScript/module/ocr/test.png"
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to read image from path: {image_path}")
    else:
        result = volc_ocr.request_ocr(image=image)
        result2 = baidu_ocr.request_ocr(image=image,model="general")
        print(result)
        # print(result2)
