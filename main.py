import os
import random
import string
import requests
from fastapi import FastAPI
from sqlalchemy import create_engine, text

# 1. SETUP KONEKSI DATABASE
# Mengambil URL dari Docker environment, jika tidak ada pakai localhost
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/country_db")
engine = create_engine(DB_URL)

# 2. FUNGSI INISIALISASI DATABASE (Self-Healing)
def init_db():
    """Memastikan tabel sudah ada di database sebelum aplikasi melayani request."""
    create_table_query = text("""
    CREATE TABLE IF NOT EXISTS country_languages (
        id SERIAL PRIMARY KEY,
        raw_id VARCHAR(13),
        user_id VARCHAR(10),
        country_name VARCHAR(255),
        cca3 VARCHAR(3),
        region VARCHAR(100),
        subregion VARCHAR(100),
        lang_code VARCHAR(10),
        lang_name VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    with engine.connect() as connection:
        connection.execute(create_table_query)
        connection.commit()
    print("--- Database Initialized Successfully ---")

# Jalankan pembuatan tabel saat script dijalankan
init_db()

app = FastAPI()

# 3. HELPER FUNCTIONS UNTUK GENERATE ID
def generate_raw_id():
    # Menghasilkan 13 karakter acak (huruf kecil dan angka)
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(13))

def generate_user_id():
    # Menghasilkan 7 digit angka acak
    return int(''.join(random.choice(string.digits) for _ in range(7)))

# 4. ENDPOINT UTAMA: FETCH AND SAVE
@app.post("/fetch-and-save")
def fetch_and_save(payload: dict):
    region = payload.get("region") # Contoh: "asia"
    
    # Ambil data dari REST Countries API
    api_url = f"https://restcountries.com/v3.1/region/{region}"
    response = requests.get(api_url)
    countries_data = response.json()
    
    # Generate ID unik untuk sesi penarikan ini
    session_raw_id = generate_raw_id()
    session_user_id = generate_user_id()
    
    final_results = []
    
    # 5. PROSES TRANSFORMASI & NORMALISASI
    for country in countries_data:
        name = country.get("name", {}).get("common")
        cca3 = country.get("cca3")
        subregion = country.get("subregion")
        languages = country.get("languages", {}) # Format API: {"kode": "nama"}
        
        # NORMALISASI: 1 Bahasa = 1 Baris (Penting untuk Task 1)
        for lang_code, lang_name in languages.items():
            with engine.connect() as connection:
                query = text("""
                    INSERT INTO country_languages 
                    (raw_id, user_id, country_name, cca3, region, subregion, lang_code, lang_name)
                    VALUES (:raw_id, :user_id, :country_name, :cca3, :region, :subregion, :lang_code, :lang_name)
                """)
                
                connection.execute(query, {
                    "raw_id": session_raw_id,
                    "user_id": str(session_user_id),
                    "country_name": name,
                    "cca3": cca3,
                    "region": region,
                    "subregion": subregion,
                    "lang_code": lang_code,
                    "lang_name": lang_name
                })
                connection.commit() # Simpan permanen ke database
            
            # Tambahkan ke daftar untuk dikembalikan sebagai respon JSON
            final_results.append({
                "country_name": name,
                "cca3": cca3,
                "subregion": subregion,
                "lang_code": lang_code,
                "lang_name": lang_name
            })

    # 6. RETURN RESPONSE SESUAI SPEK DOKUMEN
    return {
        "raw_id": session_raw_id,
        "user_id": str(session_user_id),
        "region": region,
        "total_countries": len(countries_data),
        "returned_entries": final_results
    }