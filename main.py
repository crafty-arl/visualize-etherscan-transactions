import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import networkx as nx
from neo4j import GraphDatabase
from py2neo import Graph
import numpy as np

# Function to fetch transactions from Etherscan
def fetch_transactions(address, api_key):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    return data['result']

# Convert Unix timestamp to datetime
def convert_timestamp(timestamp):
    return datetime.fromtimestamp(int(timestamp))

# Function to connect to Neo4j
def connect_to_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

# Function to clear existing data in Neo4j
def clear_neo4j_data(driver):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

# Function to create nodes and relationships in Neo4j
def create_neo4j_transactions(driver, transactions):
    with driver.session() as session:
        for tx in transactions:
            session.write_transaction(create_transaction, tx)

# Function to create a single transaction in Neo4j
def create_transaction(tx, transaction):
    query = """
    MERGE (a:Address {address: $from_address})
    MERGE (b:Address {address: $to_address})
    CREATE (a)-[:SENT {value: $value, hash: $hash, timeStamp: $timeStamp}]->(b)
    """
    tx.run(query, 
           from_address=transaction['from'], 
           to_address=transaction['to'], 
           value=int(transaction['value']) / 1e18, 
           hash=transaction['hash'], 
           timeStamp=convert_timestamp(transaction['timeStamp']))

# Function to fetch relationships from Neo4j
def fetch_neo4j_data(uri, user, password):
    graph = Graph(uri, auth=(user, password))
    query = """
    MATCH (a:Address)-[r:SENT]->(b:Address)
    RETURN a.address as from, b.address as to, r.value as value
    """
    return graph.run(query).to_data_frame()

# Streamlit app
def main():
    st.title("Ethereum Transaction Viewer")

    # Input fields for Ethereum address and API key
    address = st.text_input("Enter Ethereum Address", "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae")
    api_key = st.text_input("Enter Etherscan API Key")
    
    # Input fields for Neo4j connection
    neo4j_uri = st.text_input("Enter Neo4j URI", "bolt://<host>:<port>")
    neo4j_user = st.text_input("Enter Neo4j Username", "neo4j")
    neo4j_password = st.text_input("Enter Neo4j Password", "password")

    # Fetch and display transaction data
    if st.button("Fetch Transactions"):
        if address and api_key:
            transactions = fetch_transactions(address, api_key)
            if transactions:
                df = pd.DataFrame(transactions)
                
                # Convert timestamps to datetime
                df['timeStamp'] = df['timeStamp'].apply(lambda x: convert_timestamp(x))
                
                # Display transaction data
                st.write("Transaction Data", df)
                
                # Line graph for transactions over time
                st.write("Transactions Over Time")
                fig, ax = plt.subplots()
                df['timeStamp'] = pd.to_datetime(df['timeStamp'])
                df.set_index('timeStamp', inplace=True)
                df['value'] = df['value'].astype(float) / 1e18  # Convert Wei to Ether
                df['value'].plot(ax=ax, kind='line', figsize=(10, 5), title='Transactions Over Time')
                ax.set_xlabel("Date")
                ax.set_ylabel("Transaction Value (Ether)")
                st.pyplot(fig)

                # Bar graph for transaction volume
                st.write("Transaction Volume")
                fig, ax = plt.subplots()
                df['date'] = df.index.date
                volume = df.groupby('date').size()
                volume.plot(ax=ax, kind='bar', figsize=(10, 5), title='Transaction Volume by Date')
                ax.set_xlabel("Date")
                ax.set_ylabel("Number of Transactions")
                st.pyplot(fig)
                
                # Connect to Neo4j and create transactions
                if neo4j_uri and neo4j_user and neo4j_password:
                    driver = connect_to_neo4j(neo4j_uri, neo4j_user, neo4j_password)
                    # Clear existing data
                    clear_neo4j_data(driver)
                    # Create new transactions
                    create_neo4j_transactions(driver, transactions)
                    st.success("Transactions have been successfully added to the Neo4j database.")
                    
                    # Fetch relationships from Neo4j for visualization
                    df_neo4j = fetch_neo4j_data(neo4j_uri, neo4j_user, neo4j_password)
                    st.write("Relational Mapping Data", df_neo4j)

                    # Visualize relationships using networkx and matplotlib
                    st.write("Relational Mapping Visualization")
                    G = nx.from_pandas_edgelist(df_neo4j, 'from', 'to', ['value'])
                    
                    # Normalize the edge colors based on transaction value
                    values = df_neo4j['value'].values
                    norm = plt.Normalize(values.min(), values.max())
                    edge_colors = plt.cm.Blues(norm(values))
                    
                    pos = nx.spring_layout(G)
                    fig, ax = plt.subplots(figsize=(12, 8))
                    nx.draw(G, pos, with_labels=True, node_size=3000, node_color="skyblue", ax=ax, font_size=10, font_color="black", font_weight="bold", edge_color=edge_colors, width=2)
                    sm = plt.cm.ScalarMappable(cmap=plt.cm.Blues, norm=norm)
                    sm.set_array([])
                    plt.colorbar(sm, ax=ax, orientation='vertical', label='Transaction Value (Ether)')
                    st.pyplot(fig)
                else:
                    st.warning("Please enter Neo4j connection details.")
            else:
                st.write("No transactions found or invalid address/API key.")
        else:
            st.write("Please enter both Ethereum address and API key.")

if __name__ == "__main__":
    main()
