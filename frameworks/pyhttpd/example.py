import json
import ccxt
from osext.pyhttp.Webhook import WebhookTask
from oscore.libconfig import Config

class MyWebhook(WebhookTask):
    def on_request(body: str) -> tuple[int, dict]:
        data: dict = json.loads(body)

        strategy: str = data.get("strategy")
        mode: str = data.get("mode")
        side: str = data.get("side")
        symbol: str = data.get("symbol")
        entry: float = data.get("entry")
        stop_loss: float = data.get("stop_loss")
        qty: float = data.get("qty")
        take_profit: float = data.get("take_profit")

        # If symbol has .P ending, Remove it
        if symbol and symbol.endswith(".P"):
            symbol = symbol[:-2]


        config: Config = Config("ByBit").fetch()

        """
        {
            "api": "xxxxx",
            "sk": "xxxxxx
        }
        """

        exchange = ccxt.bybit({
            'apiKey': config['api'],
            'secret': config['sk']
        })

        exchange.enable_demo_trading(True)

        order = exchange.create_order(
            symbol=symbol,
            type='limit',
            side=side,
            amount=qty,
            price=entry,
            params={
                "postOnly": True,
                "stopLoss": {
                    "triggerPrice": stop_loss
                },
                "takeProfit": {
                    "triggerPrice": take_profit
                }
            }
        )

        return 200, {}

































if __name__ == "__main__":
    print(MyWebhook.on_request(
        json.dumps({"strategy":"Prism Comet 1.3D","mode":"Testing","side":"long","symbol":"SOLUSDT.P","entry":90.08,"stop_loss":89.98,"qty":100.00,"take_profit":90.18})
    ))