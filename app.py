import os
import openai
import streamlit as st
import psycopg2
import pandas as pd
from typing import Dict, List, Tuple

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Database connection details
DB_CONFIG = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "CqvjnWg5lA1c",
    "host": "ep-red-cherry-a5ibqtap.us-east-2.aws.neon.tech",
    "port": "5432",
    "sslmode": "require"
}

class DatabaseChatbot:
    def __init__(self, db_config: Dict[str, str]):
        """Initialize the chatbot with database configuration."""
        self.db_config = db_config
        self.conn = None
        self.system_prompt = """
        You are a helpful SQL assistant. Your task is to:
        1. Convert natural language questions into SQL queries
        2. Only generate SQL for the existing tables
        3. Ensure queries are safe and well-formatted
        4. Return only the SQL query without any explanations
        """

    def connect_to_db(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            print("Successfully connected to the database!")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise

    def get_table_schema(self) -> str:
        """Retrieve database schema information."""
        if not self.conn:
            self.connect_to_db()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        
        schema_info = cursor.fetchall()
        schema_text = "Database Schema:\n"
        current_table = ""
        
        for table, column, dtype in schema_info:
            if table != current_table:
                schema_text += f"\nTable: {table}\n"
                current_table = table
            schema_text += f"- {column} ({dtype})\n"
        
        cursor.close()
        return schema_text

    def generate_sql_query(self, question: str) -> str:
        """Generate SQL query from natural language question."""
        schema = self.get_table_schema()
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Schema:\n{schema}\n\nQuestion: {question}\n\nGenerate only the SQL query:"}
        ]
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.2
        )
        
        return response.choices[0].message.content.strip()

    def execute_query(self, query: str) -> Tuple[List[str], List[tuple]]:
        """Execute SQL query and return results."""
        if not self.conn:
            self.connect_to_db()
        
        cursor = self.conn.cursor()
        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            return columns, results
        except Exception as e:
            print(f"Error executing query: {e}")
            raise
        finally:
            cursor.close()

def main():
    st.title("💬 Database Chatbot")
    st.write("Ask questions about your database in natural language!")

    # Initialize chatbot
    chatbot = DatabaseChatbot(DB_CONFIG)

    # Create the chat input
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "data" in message:
                st.dataframe(message["data"])

    # Chat input
    if prompt := st.chat_input("Ask a question about your data"):
        # Display user message
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            # Generate and display SQL
            sql_query = chatbot.generate_sql_query(prompt)
            with st.chat_message("assistant"):
                st.write("Generated SQL Query:")
                st.code(sql_query, language="sql")
                
                # Execute query and display results
                columns, results = chatbot.execute_query(sql_query)
                df = pd.DataFrame(results, columns=columns)
                st.write("Query Results:")
                st.dataframe(df)
                
                # Save assistant message
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Here's what I found:",
                    "data": df
                })

        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()