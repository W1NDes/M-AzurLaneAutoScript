import requests
from module.log_res.log_res import logger
import base64,requests,cv2

class BaiduOcr:
    def __init__(self,config,api_key=None,secret_key=None):
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
        
    def request_baidu_ocr(self,image,area,model="general_basic"):
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
        
