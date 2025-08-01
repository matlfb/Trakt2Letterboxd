# 🎬 Trakt2Letterboxd

Python script to export your **Trakt** watched movies or lists (like your watchlist) into a **CSV** compatible with **Letterboxd**.

✅ Now supports **refresh tokens** – no more daily logins!

---

## 🔧 Setup

### 1. Install requirements

Make sure you have Python 3.7+ installed, then run:

```bash
pip install -r requirements.txt
```

### 2. Configure the script

Edit the file `Trakt2Letterboxd.py` and replace the values at the top:

```python
CLIENT_ID = "your-trakt-client-id"
CLIENT_SECRET = "your-trakt-client-secret"
```

You can get your credentials at:

🔗 https://trakt.tv/oauth/applications

---

## 🚀 Usage

Run the script:

```bash
python Trakt2Letterboxd.py
```

On the **first run**, the script will:

1. Prompt you to visit [https://trakt.tv/activate](https://trakt.tv/activate)  
2. Display an 8-digit code to enter there  
3. Save your authentication tokens into a file named `t_token`

Once authenticated, the script will create **two** CSV files:

- `trakt-exported-history.csv` — your watched history, to be imported via [Letterboxd Import](https://letterboxd.com/import/)  
- `trakt-exported-watchlist.csv` — your watchlist, to be imported via [Letterboxd Watchlist](https://letterboxd.com/watchlist/)

You can import these files directly on Letterboxd.

---

## 🔁 Token Management

- Trakt access tokens expire every **24 hours**  
- This script uses your **refresh token** to renew automatically  
- As long as you run the script **at least once every 90 days**, you won’t need to log in again  

---

## ⚠️ Warning

Never commit or share your `CLIENT_ID`, `CLIENT_SECRET`, or `t_token` file publicly.

---

## 🙏 Credits

- Forked from: [Jordy3D/Trakt2Letterboxd](https://github.com/Jordy3D/Trakt2Letterboxd)  
- Modified and updated by: [@matlfb](https://github.com/matlfb)
