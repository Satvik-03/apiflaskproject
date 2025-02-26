from flask import Flask, request, jsonify
from flask_restful import Api, Resource
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pandas as pd
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import jwt
import bcrypt
import os
from dotenv import load_dotenv  # Load environment variables

# Load environment variables from .env file
load_dotenv()

# Flask setup
app = Flask(__name__)
api = Api(app)

# Load secrets from .env file
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret_key")
MONGO_URI = os.getenv("MONGO_URI")

# Establish connection with MongoDB Atlas
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client["stock_db"]  # Your database name

# Collections
users_collection = db["users"]
stocks_collection = db["stocks"]

# Check MongoDB Connection
try:
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print("❌ MongoDB connection error:", e)


# 🔹 Helper function: Fetch stock data and store in MongoDB
def fetch_stock_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1d")

        if hist.empty:
            return {"message": "Stock data not found"}, 404

        latest_price = hist["Close"].iloc[-1]
        data = {
            "symbol": symbol,
            "latest_price": latest_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ Fixed datetime issue
        }

        # Store data in MongoDB
        stocks_collection.update_one({"symbol": symbol}, {"$set": data}, upsert=True)
        return data
    except Exception as e:
        return {"error": str(e)}, 500


# 🔹 User Registration
class Register(Resource):
    def post(self):
        try:
            data = request.json
            username = data["username"]
            password = data["password"]

            if users_collection.find_one({"username": username}):
                return {"message": "User already exists"}, 400

            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            users_collection.insert_one({"username": username, "password": hashed_password})
            return {"message": "User registered successfully"}, 201
        except Exception as e:
            return {"error": str(e)}, 500


# 🔹 User Login
class Login(Resource):
    def post(self):
        try:
            data = request.json
            username = data["username"]
            password = data["password"]

            user = users_collection.find_one({"username": username})
            if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
                return {"message": "Invalid credentials"}, 401

            token = jwt.encode(
                {"username": username, "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            return {"token": token}, 200
        except Exception as e:
            return {"error": str(e)}, 500


# 🔹 Protected Route (Requires JWT)
class StockMarketData(Resource):
    def get(self, symbol):
        token = request.headers.get("Authorization")
        if not token:
            return {"message": "Token is missing"}, 401

        try:
            jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return {"message": "Token has expired"}, 401
        except jwt.InvalidTokenError:
            return {"message": "Token is invalid"}, 401

        return fetch_stock_data(symbol), 200


# 🔹 1. Company Information Endpoint
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


# 🔹 2. Historical Market Data Endpoint
class HistoricalMarketData(Resource):
    def get(self, symbol):
        start_date = request.args.get("start")
        end_date = request.args.get("end")

        if not start_date or not end_date:
            return {"message": "Provide 'start' and 'end' query parameters in YYYY-MM-DD format."}, 400

        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty:
            return {"message": "No historical data found for the given date range."}, 404

        historical_data = {
            str(date): {
                "Open": row["Open"],
                "High": row["High"],
                "Low": row["Low"],
                "Close": row["Close"],
                "Volume": row["Volume"],
            }
            for date, row in hist.iterrows()
        }

        return jsonify(historical_data)


# 🔹 3. Analytical Insights (Simple Moving Average Strategy)
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


# 🏗 Adding Resources to API
api.add_resource(Register, "/register")
api.add_resource(Login, "/login")
api.add_resource(CompanyInfo, "/company/<string:symbol>")
api.add_resource(StockMarketData, "/stock/<string:symbol>")
api.add_resource(HistoricalMarketData, "/historical/<string:symbol>")
api.add_resource(AnalyticalInsights, "/insights/<string:symbol>")

# 🚀 Run Flask App
if __name__ == "__main__":
    app.run(debug=True)
