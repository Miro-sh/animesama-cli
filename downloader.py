import requests
import re
from bs4 import BeautifulSoup

HEADERS_BASE = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "accept-language": "en-US,en;q=0.5",
    "connection": "keep-alive"
}

class AnimeDownloader:
    def __init__(self, debug=False):
        # initialise le downloader avec une session pour les requêtes
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BASE)
        self.debug = debug

    def debug_print(self, *args, **kwargs):
        # affiche des infos de debug seulement si activé
        if self.debug:
            print("[DEBUG]", *args, **kwargs)

    def get_anime_episode(self, complete_url, filever):
        # récupère la liste des épisodes pour un anime
        complete_url = complete_url.replace('https://', '')
        url = f"https://{complete_url}/episodes.js"
        try:
            response = self.session.get(url, params={"filever": filever})
            response.raise_for_status()
            content = response.text
            
            sibnet_links = {}
            matches = re.finditer(r'https://video\.sibnet\.ru/shell\.php\?videoid=(\d+)', content)
            sibnet_links = {str(i): match.group(1) for i, match in enumerate(matches, 1)}
            
            return sibnet_links
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération des épisodes : {e}")
            return {}

    def get_video_url(self, video_id):
        # récupère l'url de la vidéo à partir de l'id
        try:
            url = f"https://video.sibnet.ru/shell.php"
            print(f"Tentative de récupération de la vidéo {video_id}...")
            response = self.session.get(url, params={"videoid": video_id})
            response.raise_for_status()
            html_content = response.text

            print("Recherche du pattern dans le contenu HTML...")
            match = re.search(r'player\.src\(\[\{src: "/v/([^/]+)/', html_content)
            if match:
                video_hash = match.group(1)
                url_sibnet = f"https://video.sibnet.ru/v/{video_hash}/{video_id}.mp4"
                print(f"URL construite : {url_sibnet}")
                
                headers_sibnet = {
                    **HEADERS_BASE,
                    "range": "bytes=0-",
                    "accept-encoding": "identity",
                    "referer": "https://video.sibnet.ru/",
                }
                response_sibnet = self.session.get(url_sibnet, headers=headers_sibnet, allow_redirects=False)
                
                if response_sibnet.status_code == 302:
                    return response_sibnet.headers['Location']
                else:
                    print(f"Status code inattendu : {response_sibnet.status_code}")
            else:
                print("Pattern non trouvé dans le HTML")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération de l'URL vidéo : {e}")
            return None

    def get_catalogue(self, query="", vf=False): 
        # récupère la liste des animes du catalogue qui correspondent à la recherche
        try:
            url = "https://anime-sama.fr/catalogue/"
            headers = {
                "host": "anime-sama.fr",
                "connection": "keep-alive",
                "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Google Chrome\";v=\"132\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": "https://anime-sama.fr/catalogue/",
                "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            querystring = {"search": query}
            if vf:
                querystring["langue[]"] = "VF"
            
            self.debug_print(f"Envoi requête GET vers: {url}")
            self.debug_print(f"Headers: {headers}")
            self.debug_print(f"Querystring: {querystring}")
            
            response = self.session.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            
            self.debug_print(f"Status code: {response.status_code}")
            self.debug_print(f"Réponse brute: {response.text}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            titles = soup.find_all('h1', class_='text-white font-bold uppercase text-md line-clamp-2')
            links = [a['href'] for a in soup.find_all('a', href=True) if 'catalogue' in a['href']]
            
            if vf:
                links = [link.replace("vostfr", "vf") for link in links]
            
            self.debug_print(f"Nombre de titres trouvés: {len(titles)}")
            self.debug_print(f"Titres trouvés: {[title.text.strip() for title in titles]}")
            
            return [title.text.strip() for title in titles], links
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération du catalogue : {e}")
            self.debug_print(f"Exception complète: {str(e)}")
            return [], []

def get_seasons(html_content):
    # récupère toutes les saisons d'un anime à partir de la page html
    seasons = []
    pattern = r'panneauAnime\("([^"]+)",\s*"([^"]+)"\)'
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    season_buttons = soup.find_all('button', {'onclick': True})
    season_divs = soup.find_all('div', class_=lambda x: x and 'saison' in x.lower())
    
    matches = re.findall(pattern, html_content)
    
    if not matches:
        return []
        
    for name, path in matches:
        if "film" not in name.lower() and name.lower() != "nom":
            seasons.append({
                'name': name,
                'url': path
            })
    
    return seasons

def get_episode_list(url):
    # extrait le numéro de version des fichiers pour récupérer les épisodes
    url = url.replace('https://', '')
    
    headers = {
        "host": "anime-sama.fr",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "connection": "keep-alive",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1"
    }

    try:
        response = requests.get(f"https://{url}", headers=headers)
        content = response.text
        
        pattern = r'episodes\.js\?filever=(\d+)'
        match = re.search(pattern, content)
        
        if match:
            filever = match.group(1)
            return filever
        return None
        
    except Exception as e:
        print(f"Erreur lors de la requête : {str(e)}")
        return None

def extract_anime_url(html_content):
    # extrait l'url d'un anime à partir du contenu html
    soup = BeautifulSoup(html_content, 'html.parser')
    link_tag = soup.find('a', href=True, class_='flex divide-x')
    if link_tag:
        return link_tag['href']
    return None 