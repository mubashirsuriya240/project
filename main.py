import os
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pyodbc
import streamlit as st

# -----------------------------
# CONFIG
# -----------------------------
RAW_DIR = "D:/Banggood_Project/data/raw"
CLEAN_DIR = "D:/Banggood_Project/data/cleaned"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)

CATEGORIES = {
    "phones": "https://www.banggood.com/search/phones.html?from=nav&page={}",
    "smartwatches": "https://www.banggood.com/search/smartwatches.html?from=nav&page={}",
    "laptops": "https://www.banggood.com/search/laptops.html?from=nav&page={}",
    "rc_drones": "https://www.banggood.com/search/rc-drones.html?from=nav&page={}",
    "home_appliances": "https://www.banggood.com/search/home-appliances.html?from=nav&page={}"
}
MAX_PAGES = 5

SQL_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "DESKTOP-CJ2TM4F",
    "database": "BanggoodDB"
}

# -----------------------------
# Selenium driver
# -----------------------------
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

# -----------------------------
# Scraping function
# -----------------------------
def scrape_category(category_name, url_template):
    driver = get_driver()
    all_products = []
    print(f"\nScraping category: {category_name}")

    for page in tqdm(range(1, MAX_PAGES + 1), desc=f"{category_name} pages"):
        url = url_template.format(page)
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        items = driver.find_elements(By.CSS_SELECTOR, "div.p-wrap")
        if not items:
            break

        for item in items:
            try: title_elem = item.find_element(By.CSS_SELECTOR, "a.title"); name = title_elem.text.strip(); product_url = title_elem.get_attribute("href")
            except: name, product_url = None, None
            try: price = item.find_element(By.CSS_SELECTOR, "span.price").text.strip()
            except: price = None
            try: old_price = item.find_element(By.CSS_SELECTOR, "span.price-old").text.strip()
            except: old_price = None
            try: discount = item.find_element(By.CSS_SELECTOR, "span.price-discount").text.strip()
            except: discount = None
            try: reviews = item.find_element(By.CSS_SELECTOR, "a.review").text.strip()
            except: reviews = None
            try: rating = item.find_element(By.CSS_SELECTOR, "span.review-text").text.strip()
            except: rating = None

            all_products.append({
                "category": category_name,
                "product_name": name,
                "product_url": product_url,
                "price": price,
                "old_price": old_price,
                "discount": discount,
                "reviews": reviews,
                "rating": rating
            })
        time.sleep(random.uniform(1, 2))
    driver.quit()
    
    output_file = os.path.join(RAW_DIR, f"{category_name}_raw.csv")
    df = pd.DataFrame(all_products)
    df.to_csv(output_file, index=False)
    print(f"Saved {len(all_products)} items to {output_file}")
    return df

# -----------------------------
# Cleaning & Transformation
# -----------------------------
def clean_data(df):
    df['price'] = pd.to_numeric(df['price'].astype(str).str.replace(r'[^\d.]','',regex=True), errors='coerce')
    df['old_price'] = pd.to_numeric(df['old_price'].astype(str).str.replace(r'[^\d.]','',regex=True), errors='coerce')
    df['discount'] = pd.to_numeric(df['discount'].astype(str).str.replace(r'[^\d.]','',regex=True), errors='coerce')
    df['reviews'] = pd.to_numeric(df['reviews'].astype(str).str.extract(r'(\d+)')[0], errors='coerce')
    df['rating'] = pd.to_numeric(df['rating'].astype(str).str.extract(r'([\d.]+)')[0], errors='coerce')
    df.fillna({'old_price': df['price'], 'discount':0, 'reviews':0, 'rating':0}, inplace=True)
    df['price_drop'] = df['old_price'] - df['price']
    df['value_score'] = df['rating'] * df['reviews'] / (df['price']+1)
    return df

# -----------------------------
# Exploratory Analysis
# -----------------------------
def exploratory_analysis(df):
    sns.set(style="whitegrid")
    # Price distribution
    plt.figure(figsize=(10,6))
    sns.histplot(df, x='price', hue='category', bins=50, kde=True)
    plt.title("Price Distribution by Category")
    plt.savefig(os.path.join(CLEAN_DIR, "price_distribution.png"))
    plt.close()
    # Rating vs Price
    plt.figure(figsize=(10,6))
    sns.scatterplot(df, x='price', y='rating', hue='category')
    plt.title("Rating vs Price")
    plt.savefig(os.path.join(CLEAN_DIR, "rating_vs_price.png"))
    plt.close()
    # Top 10 Reviews
    top_reviews = df.sort_values('reviews', ascending=False).head(10)
    plt.figure(figsize=(12,6))
    sns.barplot(top_reviews, x='product_name', y='reviews', palette='viridis')
    plt.xticks(rotation=45)
    plt.title("Top 10 Reviewed Products")
    plt.savefig(os.path.join(CLEAN_DIR, "top10_reviews.png"))
    plt.close()
    # Price drop boxplot
    plt.figure(figsize=(10,6))
    sns.boxplot(df, x='category', y='price_drop')
    plt.title("Price Drop Distribution")
    plt.savefig(os.path.join(CLEAN_DIR, "price_drop.png"))
    plt.close()
    # Value score boxplot
    plt.figure(figsize=(10,6))
    sns.boxplot(df, x='category', y='value_score')
    plt.title("Value Score Distribution")
    plt.savefig(os.path.join(CLEAN_DIR, "value_score.png"))
    plt.close()
    print("EDA Charts saved in cleaned folder.")

# -----------------------------
# SQL Deployment
# -----------------------------
def deploy_to_sql(df):
    # Create DB if not exists
    conn_master = pyodbc.connect(f"DRIVER={SQL_CONFIG['driver']};SERVER={SQL_CONFIG['server']};Trusted_Connection=yes;", autocommit=True)
    cursor_master = conn_master.cursor()
    cursor_master.execute(f"IF DB_ID('{SQL_CONFIG['database']}') IS NULL CREATE DATABASE {SQL_CONFIG['database']};")
    conn_master.close()
    conn = pyodbc.connect(f"DRIVER={SQL_CONFIG['driver']};SERVER={SQL_CONFIG['server']};DATABASE={SQL_CONFIG['database']};Trusted_Connection=yes;")
    cursor = conn.cursor()
    cursor.execute("""
        IF OBJECT_ID('banggood_products', 'U') IS NULL
        CREATE TABLE banggood_products (
            id INT IDENTITY(1,1) PRIMARY KEY,
            category VARCHAR(100),
            product_name VARCHAR(255),
            product_url VARCHAR(500) UNIQUE,
            price DECIMAL(10,2),
            old_price DECIMAL(10,2),
            discount INT,
            reviews INT,
            rating DECIMAL(3,2),
            price_drop DECIMAL(10,2),
            value_score DECIMAL(10,2)
        )
    """)
    conn.commit()
    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO banggood_products
                (category, product_name, product_url, price, old_price, discount, reviews, rating, price_drop, value_score)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, row['category'], row['product_name'], row.get('product_url',''), row['price'], row['old_price'], int(row['discount']), int(row['reviews']), float(row['rating']), row['price_drop'], row['value_score'])
        except:
            continue
    conn.commit()
    conn.close()
    print("✅ Data deployed to SQL Server successfully!")

# -----------------------------
# Streamlit Dashboard
# -----------------------------
def streamlit_dashboard():
    st.set_page_config(page_title="Banggood Dashboard", layout="wide")
    st.title("📊 Banggood Products Dashboard")

    conn = pyodbc.connect(f"DRIVER={SQL_CONFIG['driver']};SERVER={SQL_CONFIG['server']};DATABASE={SQL_CONFIG['database']};Trusted_Connection=yes;")
    df_sql = pd.read_sql("SELECT * FROM banggood_products", conn)
    conn.close()

    st.subheader("Top 10 Products by Reviews")
    top_reviews = df_sql.sort_values('reviews', ascending=False).head(10)
    st.dataframe(top_reviews[['product_name','reviews','category']])

    st.subheader("Category Distribution")
    category_counts = df_sql['category'].value_counts()
    fig1, ax1 = plt.subplots(figsize=(6,6))
    category_counts.plot.pie(autopct='%1.1f%%', startangle=140, ax=ax1, cmap='Set3')
    ax1.set_ylabel('')
    st.pyplot(fig1)

    st.subheader("Top 10 Products Bar Chart")
    fig2, ax2 = plt.subplots(figsize=(12,6))
    sns.barplot(x='reviews', y='product_name', data=top_reviews, palette='viridis', ax=ax2)
    ax2.set_xlabel("Reviews")
    ax2.set_ylabel("Product Name")
    st.pyplot(fig2)

    st.subheader("Price Drop Distribution by Category")
    fig3, ax3 = plt.subplots(figsize=(10,6))
    sns.boxplot(x='category', y='price_drop', data=df_sql, ax=ax3)
    ax3.set_title("Price Drop Distribution")
    st.pyplot(fig3)

    st.subheader("Value Score Distribution by Category")
    fig4, ax4 = plt.subplots(figsize=(10,6))
    sns.boxplot(x='category', y='value_score', data=df_sql, ax=ax4)
    ax4.set_title("Value Score Distribution")
    st.pyplot(fig4)

    st.success("✅ Dashboard Loaded Successfully!")

# -----------------------------
# Main
# -----------------------------
def main_pipeline(run_dashboard=False):
    all_dfs = []
    for cat, url in CATEGORIES.items():
        df_raw = scrape_category(cat, url)
        df_clean = clean_data(df_raw)
        all_dfs.append(df_clean)
    df_all = pd.concat(all_dfs, ignore_index=True)
    df_all.to_csv(os.path.join(CLEAN_DIR, "banggood_cleaned.csv"), index=False)
    exploratory_analysis(df_all)
    deploy_to_sql(df_all)
    if run_dashboard:
        streamlit_dashboard()

# -----------------------------
# Run
# -----------------------------
if _name_ == "_main_":
    main_pipeline(run_dashboard=True)