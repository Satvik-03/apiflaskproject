from flask import Flask, request, jsonify
from flask_restful import Api, Resource
import yfinance as yf
from datetime import datetime

app = Flask(__name__)
api = Api(app)

# 1. Company Information Endpoint
class CompanyInfo(Resource):
    def get(self, symbol):
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            return {
                "symbol": symbol,
                "name": info.get("longName"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "sector": info.get("sector"),
                "website": info.get("website"),
            }, 200
        except Exception as e:
            return {"error": str(e)}, 500

# 2. Stock Market Data (Real-time) Endpoint
class StockMarketData(Resource):
    def get(self, symbol):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1d")
            latest_price = hist["Close"].iloc[-1]
            return {"symbol": symbol, "latest_price": latest_price}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# 3. Historical Market Data Endpoint
class HistoricalMarketData(Resource):
    def get(self, symbol):
        start_date = request.args.get("start")
        end_date = request.args.get("end")

        if not start_date or not end_date:
            return {"message": "Please provide 'start' and 'end' query parameters in YYYY-MM-DD format."}, 400

        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty:
            return {"message": "No historical data found for the given date range."}, 404

        # Convert Timestamp index to string format
        historical_data = {
            str(date): {"Open": row["Open"], "High": row["High"], "Low": row["Low"], "Close": row["Close"], "Volume": row["Volume"]}
            for date, row in hist.iterrows()
        }

        return jsonify(historical_data)

# 4. Analytical Insights (Simple Moving Average Strategy)
class AnalyticalInsights(Resource):
    def get(self, symbol):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            hist["SMA_50"] = hist["Close"].rolling(window=50).mean()
            hist["SMA_200"] = hist["Close"].rolling(window=200).mean()
            
            latest_sma_50 = hist["SMA_50"].iloc[-1]
            latest_sma_200 = hist["SMA_200"].iloc[-1]
            latest_price = hist["Close"].iloc[-1]

            if latest_sma_50 > latest_sma_200 and latest_price > latest_sma_50:
                recommendation = "BUY"
            elif latest_sma_50 < latest_sma_200 and latest_price < latest_sma_50:
                recommendation = "SELL"
            else:
                recommendation = "HOLD"

            return {"symbol": symbol, "recommendation": recommendation}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# Adding Resources to API
api.add_resource(CompanyInfo, "/company/<string:symbol>")
api.add_resource(StockMarketData, "/stock/<string:symbol>")
api.add_resource(HistoricalMarketData, "/historical/<string:symbol>")
api.add_resource(AnalyticalInsights, "/insights/<string:symbol>")

if __name__ == "__main__":
    app.run(debug=True)
