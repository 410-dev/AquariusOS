import json
import aeons.libmobilenotification as dove
from osext.pyhttp.Webhook import WebhookTask
from oscore.libconfig import Config

class MyWebhook(WebhookTask):
    def on_request(body: str) -> tuple[int, dict]:
        data: dict = json.loads(body)
        url: str = Config("MyDiscord").fetch().get("Server1", {}).get("Webhook1_URL", "")
        message: str = f"""Trading Idea: 
                           Time: {data['time']}
                           Ticker: {data['ticker']}
                           Side: {data['qty']}
                           Amount: {data['qty']}
                           """
        dove.curl(url, message)
        return 0, {}
