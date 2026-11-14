# "What would the AI crowd rate my website?": wiring (for Daniel)

Engine: `say/predict.py` (commit 19ec15f, 9 tests). Jayden asked for it at ~1:33 PM ET.
It predicts the average score our 200-shopper AI crowd would give a new store's website (1-10) and
"likely to buy" (1-10), with a measured typical error. EXPLORATORY; label everything ESTIMATE.

Key finding to show next to it: the crowd rated 12 real brands' websites between 5.7 and 7.0 out of 10,
so it rates almost every site about the same. Guessing the average is already off by only ~0.26 on the
website score (leave-one-out on 12 brands, computed by code).

## Server: `frontend/server.py`
After the trust_check import:
```python
try:  # predicted AI-crowd score (say/predict.py)
    from say import predict as crowd_predict  # type: ignore
    PRED_DATA = crowd_predict.load(crowd_predict.DATA)
    PRED_VAL = crowd_predict.load(crowd_predict.VALIDATION) if os.path.exists(crowd_predict.VALIDATION) else None
except Exception:  # noqa: BLE001
    crowd_predict = None
```
At the top of `do_POST` (next to /api/trust-check):
```python
        if self.path.split("?")[0] == "/api/predict":
            if crowd_predict is None:
                return self._json(503, {"error": "predictor not available"})
            try:
                n = min(int(self.headers.get("Content-Length", "0")), 8_000)
                data = json.loads(self.rfile.read(n) or b"{}")
                return self._json(200, crowd_predict.predict(str(data.get("store", "")), PRED_DATA, PRED_VAL, llm=LLM_CLIENT))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
```
POST `{"store": "Hand-made soy candles, sold only online"}`.

## Show (suggest: in the "Check my crowd" tab, under the trust answer, using the same "What do you sell?" text)
- `headline` (big): "Our AI crowd would likely rate your website about 6.1/10 (give or take 0.3)..."
- tag: `label` ("ESTIMATE: predicted AI-crowd score (SYNTHETIC), not what real shoppers think")
- small: `predicted_buy_score` with `typical_error.buy`, `method` (model vs average), `why` lines
- `reality_note` (always show): a good prediction of the AI crowd is not a prediction of real buyers (0.03).
