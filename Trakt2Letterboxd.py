import os
import csv
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Use the directory where this script is located
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

class TraktImporter:
    """ Trakt Importer """

    def __init__(self):
        self.api_root = 'https://api.trakt.tv'
        self.api_clid = 'b04da548cc9df60510eac7ec1845ab98cebd8008a9978804a981bff7e73ab270'
        self.api_clsc = 'a880315fba01a5e5f0ad7de12b7872e36826a9359b2f419122a24dee1b2cb600'
        self.api_token = None
        self.refresh_token = None
        self.config_path = BASE_PATH
        self.token_data_path = os.path.join(BASE_PATH, "t_token")
        self.api_headers = {'Content-Type': 'application/json'}

    def authenticate(self):
        if self.__load_token_from_cache():
            if not self.__token_valid():
                if not self.__refresh_token():
                    print("⚠️ Unable to refresh the token, manual re-authentication may be required.")
                    return False
            return True

        dev_code_details = self.__generate_device_code()
        self.__show_auth_instructions(dev_code_details)

        got_token = self.__poll_for_auth(dev_code_details['device_code'],
                                         dev_code_details['interval'],
                                         dev_code_details['expires_in'] + time.time())

        if got_token:
            self.__save_token_to_cache()
            return True

        return False

    def __load_token_from_cache(self):
        if not os.path.isfile(self.token_data_path):
            return False
        with open(self.token_data_path, 'r') as f:
            data = json.load(f)
            self.api_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
        return True

    def __save_token_to_cache(self):
        with open(self.token_data_path, 'w') as f:
            json.dump({
                'access_token': self.api_token,
                'refresh_token': self.refresh_token
            }, f)

    def __refresh_token(self):
        print("Refreshing token...")
        url = self.api_root + '/oauth/token'
        data = json.dumps({
            "refresh_token": self.refresh_token,
            "client_id": self.api_clid,
            "client_secret": self.api_clsc,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "refresh_token"
        }).encode('utf8')

        request = Request(url, data, self.api_headers)

        try:
            response_body = urlopen(request).read()
            response_data = json.loads(response_body)
            self.api_token = response_data['access_token']
            self.refresh_token = response_data['refresh_token']
            self.__save_token_to_cache()
            print("✅ Token successfully refreshed")
            return True
        except (HTTPError, URLError) as e:
            print(f"❌ Error while refreshing token: {e}")
            return False

    def __token_valid(self):
        test_url = self.api_root + '/users/me'
        headers = {
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }
        request = Request(test_url, headers=headers)

        try:
            urlopen(request)
            return True
        except HTTPError:
            return False

    def __generate_device_code(self):
        url = self.api_root + '/oauth/device/code'
        data = json.dumps({"client_id": self.api_clid}).encode('utf8')
        request = Request(url, data, self.api_headers)
        response_body = urlopen(request).read()
        return json.loads(response_body)

    @staticmethod
    def __show_auth_instructions(details):
        message = (f"\n👉 Go to {details['verification_url']} and enter the code: {details['user_code']}\n")
        print(message)

    def __poll_for_auth(self, device_code, interval, expiry):
        url = self.api_root + '/oauth/device/token'
        data = json.dumps({
            "code": device_code,
            "client_id": self.api_clid,
            "client_secret": self.api_clsc
        }).encode('utf8')
        request = Request(url, data, self.api_headers)

        while time.time() < expiry:
            time.sleep(interval)
            try:
                response_body = urlopen(request).read()
                response_data = json.loads(response_body)
                self.api_token = response_data['access_token']
                self.refresh_token = response_data['refresh_token']
                print("✅ Authenticated!")
                return True
            except HTTPError as err:
                if err.code != 400:
                    print(f"\n{err.code}: Authorization failed")
                    return False
        return False

    def get_comments(self):
        print("Getting comments/reviews...")
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }
        
        comments_dict = {}
        page = 1
        
        while True:
            request = Request(
                self.api_root + f'/users/me/comments/movies?page={page}&limit=100',
                headers=headers
            )
            try:
                response = urlopen(request)
                response_body = response.read()
                comments = json.loads(response_body)
                if not comments:
                    break
                
                for item in comments:
                    if 'movie' in item and 'comment' in item:
                        movie_ids = item['movie']['ids']
                        if isinstance(item['comment'], dict):
                            comment_text = item['comment'].get('comment', '')
                            spoiler = item['comment'].get('spoiler', False)
                        else:
                            comment_text = item['comment']
                            spoiler = item.get('spoiler', False)
                        
                        if spoiler:
                            comment_text = "[SPOILER] " + comment_text
                        
                        key = movie_ids.get('tmdb')
                        if key:
                            comments_dict[key] = comment_text
                
                print(f"Completed comments page {page}")
                page += 1
                
            except HTTPError as err:
                if err.code == 404:
                    break
                print(f"{err.code} error while fetching comments.")
                break
        
        print(f"Found {len(comments_dict)} comments/reviews")
        return comments_dict

    def get_movie_list(self, list_name):
        print(f"Getting {list_name}")
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }
        extracted_movies = []
        page = 1
        ratings = self.get_ratings()
        comments = self.get_comments()

        while True:
            request = Request(self.api_root + f'/sync/{list_name}/movies?page={page}&limit=100', headers=headers)
            try:
                response = urlopen(request)
                response_body = response.read()
                movies = json.loads(response_body)
                if not movies:
                    break
                extracted_movies.extend(self.__extract_fields(movies, ratings, comments))
                print(f"Completed page {page}")
                page += 1
            except HTTPError as err:
                print(f"{err.code} error while fetching {list_name}. Try re-authenticating manually.")
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
            response_body = response.read()
            return [
                {
                    'rating': r['rating'],
                    'imdb': r['movie']['ids']['imdb'],
                    'trakt': r['movie']['ids']['trakt'],
                    'tmdb': r['movie']['ids']['tmdb'],
                    'slug': r['movie']['ids']['slug']
                } for r in json.loads(response_body)
            ]
        except HTTPError as err:
            print(f"{err.code} error while fetching ratings. Try re-authenticating manually.")
            quit()

    @staticmethod
    def __get_rating(ratings, ids):
        for rating in ratings:
            if ids['imdb'] == rating['imdb'] or ids['trakt'] == rating['trakt'] or ids['tmdb'] == rating['tmdb'] or ids['slug'] == rating['slug']:
                return rating['rating']
        return ''

    @staticmethod
    def __get_comment(comments_dict, ids):
        tmdb_id = ids.get('tmdb')
        if tmdb_id and tmdb_id in comments_dict:
            return comments_dict[tmdb_id]
        return ''

    @staticmethod
    def __extract_fields(movies, ratings, comments):
        return [{
            'WatchedDate': x['watched_at'] if 'watched_at' in x else '',
            'tmdbID': x['movie']['ids']['tmdb'],
            'imdbID': x['movie']['ids']['imdb'],
            'Title': x['movie']['title'],
            'Year': x['movie']['year'],
            'Rating10': TraktImporter.__get_rating(ratings, x['movie']['ids']),
            'Review': TraktImporter.__get_comment(comments, x['movie']['ids'])
        } for x in movies]


def write_csv(history, filename):
    if history:
        custom_path = os.path.join(BASE_PATH, filename)
        with open(custom_path, 'w', encoding='utf8') as f:
            writer = csv.DictWriter(f, list(history[0].keys()))
            writer.writeheader()
            writer.writerows(history)
        return True
    return False


def run():
    print("Initializing...")
    importer = TraktImporter()
    if importer.authenticate():
        history = importer.get_movie_list('history')
        watchlist = importer.get_movie_list('watchlist')

        # Export complet
        if write_csv(history, "trakt-exported-history.csv"):
            print("\n✅ Your full history has been exported.")

        # Export des 50 derniers films vus
        if history:
            last_50 = history[:50]  # les 50 plus récents
            if write_csv(last_50, "trakt-exported-history-last50.csv"):
                print("✅ The last 50 movies have been exported.")

        # Export watchlist
        if write_csv(watchlist, "trakt-exported-watchlist.csv"):
            print("✅ Your watchlist has been exported.")


if __name__ == '__main__':
    run()
