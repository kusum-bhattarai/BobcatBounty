from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import logging
import traceback
import openai

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OpenAI API setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# Database connection details
DB_CONNECTION = {
    "dbname": os.getenv("DB_NAME", "neondb"),
    "user": os.getenv("DB_USER", "neondb_owner"),
    "password": os.getenv("DB_PASSWORD", "CqvjnWg5lA1c"),
    "host": os.getenv("DB_HOST", "ep-red-cherry-a5ibqtap.us-east-2.aws.neon.tech"),
    "port": os.getenv("DB_PORT", "5432")
}

# Flask app setup
app = Flask(__name__)
CORS(app)

class DatabaseConnection:
    """Context manager for database connections"""
    def __enter__(self):
        self.conn = psycopg2.connect(
            **DB_CONNECTION, sslmode="require", cursor_factory=RealDictCursor
        )
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

@app.route('/chat', methods=['POST'])
def chatbot():
    """Main chatbot endpoint to handle user queries."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"reply": "No data provided"}), 400

        user_message = data.get("message", "").lower()
        if not user_message:
            return jsonify({"reply": "Please provide a message."}), 400

        # Route message based on keywords
        if any(keyword in user_message for keyword in ["vegan", "vegetarian", "gluten free"]):
            reply = check_item_dietary_info(user_message)
        elif "in stock" in user_message:
            reply = check_item_stock(user_message)
        elif "request" in user_message:
            reply = add_item_request(user_message)
        else:
            reply = get_openai_response(user_message)

        return jsonify({"reply": reply})

    except Exception as e:
        logger.error(f"Error in chatbot: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"reply": "An error occurred. Please try again later."}), 500

def check_item_dietary_info(user_message):
    """Check if an item is vegan, vegetarian, or gluten-free."""
    try:
        item_name = extract_item_name(user_message)
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT name, vegan, gluten_free 
                    FROM products1 
                    WHERE name ILIKE %s;
                    """,
                    (f"%{item_name}%",)
                )
                result = cur.fetchone()

        if result:
            dietary_info = []
            if result["vegan"]:
                dietary_info.append("vegan")
            if result["gluten_free"]:
                dietary_info.append("gluten-free")
            return f"{result['name']} is {', '.join(dietary_info)}." if dietary_info else f"{result['name']} is neither vegan nor gluten-free."
        return f"No dietary information found for '{item_name}'."

    except Exception as e:
        logger.error(f"Error checking dietary info: {e}")
        logger.error(traceback.format_exc())
        return "Sorry, I couldn't retrieve dietary information. Please try again."

def check_item_stock(user_message):
    """Check if an item is in stock."""
    try:
        item_name = extract_item_name(user_message)
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT name, quantity 
                    FROM products1 
                    WHERE name ILIKE %s;
                    """,
                    (f"%{item_name}%",)
                )
                result = cur.fetchone()

        if result:
            return f"{result['name']} is {'in stock' if result['quantity'] > 0 else 'out of stock'} with {result['quantity']} units available."
        return f"No stock information found for '{item_name}'."

    except Exception as e:
        logger.error(f"Error checking stock: {e}")
        logger.error(traceback.format_exc())
        return "Sorry, I couldn't retrieve stock information. Please try again."

def add_item_request(user_message):
    """Add an item request to the database."""
    try:
        item_name = extract_item_name(user_message)
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO requests (item_name, request_date) 
                    VALUES (%s, NOW()) 
                    RETURNING request_id;
                    """,
                    (item_name,)
                )
                conn.commit()
        return f"Your request for '{item_name}' has been recorded."

    except Exception as e:
        logger.error(f"Error adding item request: {e}")
        logger.error(traceback.format_exc())
        return "Sorry, I couldn't process your request. Please try again."

def extract_item_name(user_message):
    """Extract item name from user message."""
    keywords = ["is", "have", "request", "stock"]
    for keyword in keywords:
        if keyword in user_message:
            return user_message.split(keyword, 1)[-1].strip()
    return user_message

def get_openai_response(user_message):
    """Get a response from OpenAI for general queries."""
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Answer this query: {user_message}",
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].text.strip()
    except Exception as e:
        logger.error(f"Error with OpenAI API: {e}")
        return "Sorry, I couldn't process your query with OpenAI. Please try again."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
