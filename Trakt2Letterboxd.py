import os
import csv
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

class TraktImporter:
    """ Trakt Importer """

    def __init__(self):
        # === CONFIGURATION UTILISATEUR ===
        self.api_root = 'https://api.trakt.tv'
        self.api_clid = 'YOUR_CLIENT_ID_HERE'        # <-- Remplace par ton client_id
        self.api_clsc = 'YOUR_CLIENT_SECRET_HERE'    # <-- Remplace par ton client_secret
        
        # Dossier où seront stockés tokens et fichiers d’export
        self.config_path = "./config"
        if not os.path.exists(self.config_path):
            os.makedirs(self.config_path)
        
        # Chemin complet vers le fichier token
        self.token_path = os.path.join(self.config_path, "t_token")
        
        self.api_token = None
        self.api_headers = { 'Content-Type': 'application/json' }

    def authenticate(self):
        if self.__decache_token():
            return True

        dev_code_details = self.__generate_device_code()
        self.__show_auth_instructions(dev_code_details)

        return self.__poll_for_auth(dev_code_details['device_code'],
                                    dev_code_details['interval'],
                                    dev_code_details['expires_in'] + time.time())

    def __decache_token(self):
        if not os.path.isfile(self.token_path):
            return False

        with open(self.token_path, 'r') as token_file:
            token_data = json.load(token_file)

        if time.time() > token_data.get('expires_at', 0):
            return self.__refresh_token(token_data.get('refresh_token'))

        self.api_token = token_data.get('access_token')
        return True

    def __encache_token(self, token_data):
        with open(self.token_path, 'w') as token_file:
            json.dump(token_data, token_file)

    def __refresh_token(self, refresh_token):
        url = self.api_root + '/oauth/token'
        data = json.dumps({
            "refresh_token": refresh_token,
            "client_id": self.api_clid,
            "client_secret": self.api_clsc,
            "grant_type": "refresh_token"
        }).encode('utf8')

        request = Request(url, data, self.api_headers)

        try:
            response = urlopen(request).read()
            response_dict = json.loads(response)
            self.api_token = response_dict['access_token']
            self.__encache_token({
                'access_token': response_dict['access_token'],
                'refresh_token': response_dict['refresh_token'],
                'expires_at': time.time() + response_dict['expires_in']
            })
            print("Access token refreshed successfully.")
            return True
        except HTTPError as err:
            print(f"{err.code} : Token refresh failed.")
            return False

    @staticmethod
    def __delete_token_cache(path):
        if os.path.exists(path):
            os.remove(path)

    def __generate_device_code(self):
        url = self.api_root + '/oauth/device/code'
        data = json.dumps({"client_id": self.api_clid}).encode('utf8')

        request = Request(url, data, self.api_headers)
        response_body = urlopen(request).read()
        return json.loads(response_body)

    @staticmethod
    def __show_auth_instructions(details):
        print(f"""
Go to {details['verification_url']} in your web browser and enter the code:

{details['user_code']}

After you've authenticated, return here to continue.
""")

    def __poll_for_auth(self, device_code, interval, expiry):
        url = self.api_root + '/oauth/device/token'
        data = json.dumps({
            "code": device_code,
            "client_id": self.api_clid,
            "client_secret": self.api_clsc
        }).encode('utf8')

        request = Request(url, data, self.api_headers)

        print("Waiting for authorization", end='', flush=True)

        while True:
            time.sleep(interval)

            try:
                response_body = urlopen(request).read()
                break
            except HTTPError as err:
                if err.code == 400:
                    print(".", end='', flush=True)
                else:
                    print(f"\n{err.code}: Authorization failed. Script will exit.")
                    return False

            if time.time() > expiry:
                print("\nAuthorization timeout.")
                return False

        response_dict = json.loads(response_body)
        if 'access_token' in response_dict:
            self.api_token = response_dict['access_token']
            self.__encache_token({
                'access_token': response_dict['access_token'],
                'refresh_token': response_dict['refresh_token'],
                'expires_at': time.time() + response_dict['expires_in']
            })
            print("\nAuthenticated!")
            return True

        return False

    def get_movie_list(self, list_name):
        print(f"Getting {list_name}")
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }

        extracted_movies = []
        page_limit = 1
        page = 1
        ratings = self.get_ratings()

        while page <= page_limit:
            request = Request(f"{self.api_root}/sync/{list_name}/movies?page={page}&limit=10", headers=headers)
            try:
                response = urlopen(request)
                page_limit = int(response.info().get('X-Pagination-Page-Count', 1))
                print(f"Completed page {page} of {page_limit}")
                page += 1
                extracted_movies.extend(self.__extract_fields(json.loads(response.read()), ratings))
            except HTTPError as err:
                if err.code in (401, 403):
                    print("Auth token expired.")
                    self.__delete_token_cache(self.token_path)
                print(f"{err.code}: An error occurred. Please re-run the script.")
                quit()

        return extracted_movies

    def get_ratings(self):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }

        request = Request(self.api_root + '/sync/ratings/movies', headers=headers)

        try:
            response = urlopen(request)
            return [
                {
                    'rating': r['rating'],
                    'imdb': r['movie']['ids']['imdb'],
                    'trakt': r['movie']['ids']['trakt'],
                    'tmdb': r['movie']['ids']['tmdb'],
                    'slug': r['movie']['ids']['slug']
                } for r in json.loads(response.read())
            ]
        except HTTPError as err:
            if err.code in (401, 403):
                print("Auth token expired.")
                self.__delete_token_cache(self.token_path)
            print(f"{err.code}: An error occurred. Please re-run the script.")
            quit()

    @staticmethod
    def __get_rating(ratings, ids):
        for r in ratings:
            if ids['imdb'] == r['imdb'] or ids['trakt'] == r['trakt'] or ids['tmdb'] == r['tmdb'] or ids['slug'] == r['slug']:
                return r['rating']
        return ''

    @staticmethod
    def __extract_fields(movies, ratings):
        return [{
            'WatchedDate': m.get('watched_at', ''),
            'tmdbID': m['movie']['ids']['tmdb'],
            'imdbID': m['movie']['ids']['imdb'],
            'Title': m['movie']['title'],
            'Year': m['movie']['year'],
            'Rating10': TraktImporter.__get_rating(ratings, m['movie']['ids'])
        } for m in movies]

def write_csv(rows, filename):
    if rows:
        with open(filename, 'w', encoding='utf8') as f:
            writer = csv.DictWriter(f, list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return True
    return False

def run():
    print("Initializing...")

    importer = TraktImporter()
    if importer.authenticate():
        history = importer.get_movie_list('history')
        watchlist = importer.get_movie_list('watchlist')

        if write_csv(history, "trakt-exported-history.csv"):
            print("✅ History exported to 'trakt-exported-history.csv'")
        else:
            print("⚠️ No history found.")

        if write_csv(watchlist, "trakt-exported-watchlist.csv"):
            print("✅ Watchlist exported to 'trakt-exported-watchlist.csv'")
        else:
            print("⚠️ No watchlist found.")

if __name__ == '__main__':
    run()
