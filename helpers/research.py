"""Source-aware extractive research. Web content remains data, never code."""
import re
import urllib.parse
from html.parser import HTMLParser
from core.dialogue import tokens


class ReadableText(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script','style','nav','footer','header','noscript','svg'}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {'script','style','nav','footer','header','noscript','svg'} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def relevant(query, title, content):
    query_words = tokens(query) - {'pesquise','pesquisar','aprenda','aprender','sobre','what','is','how','the','does','como','funciona','funcionam','que','um','uma','are','you','your','do','i','am','is','about','tell','me'}
    found = query_words & tokens(title + ' ' + content)
    return bool(query_words) and len(found) / len(query_words) >= .5


def extract(query, text):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) >= 30]
    query_words = tokens(query)
    scored = sorted(enumerate(sentences), key=lambda item: (len(tokens(item[1]) & query_words), -item[0]), reverse=True)
    selected = sorted(scored[:3], key=lambda item: item[0])
    return ' '.join(s for _,s in selected)[:850].strip()


class Researcher:
    def __init__(self, web):
        self.web = web

    def from_url(self, query, url):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return None
        try:
            with self.web._open_request(url) as response:
                kind = response.headers.get('Content-Type','')
                if not any(t in kind for t in ('text/html','text/plain')):
                    return None
                raw = self.web._read_payload(response)
                text = raw.decode('utf-8',errors='replace')
            if 'html' in kind:
                parser=ReadableText();parser.feed(text);text=' '.join(parser.parts)
            summary=extract(query,text)
            if summary and relevant(query,parsed.hostname,text):
                return {'answer':summary,'sources':[{'title':parsed.hostname,'url':url}], 'method':'extractive'}
        except Exception:
            return None
        return None

    def search(self, query):
        encoded=urllib.parse.quote(query)
        # Prefer source-bearing abstracts. RelatedTopics are not an answer.
        try:
            data=self.web._fetch_json('https://api.duckduckgo.com/?q='+encoded+'&format=json&no_html=1&skip_disambig=1')
            text=data.get('AbstractText','');title=data.get('Heading','');url=data.get('AbstractURL','')
            if url.startswith('https://') and len(text)>40 and relevant(query,title,text):
                return {'answer':extract(query,text),'sources':[{'title':title,'url':url}], 'method':'extractive'}
        except Exception:
            pass
        from helpers.config import get_env
        first='pt' if get_env('LANGUAGE','en').lower().startswith('pt') or re.search(r'\b(como|qual|sobre|funciona|o que)\b',query.lower()) else 'en'
        for language in (first, 'en' if first=='pt' else 'pt'):
            try:
                root=f'https://{language}.wikipedia.org'
                search=self.web._fetch_json(root+'/w/api.php?action=opensearch&search='+encoded+'&limit=2&namespace=0&format=json')
                for title in search[1][:2]:
                    data=self.web._fetch_json(root+'/api/rest_v1/page/summary/'+urllib.parse.quote(title,safe=''))
                    text=data.get('extract','');url=data.get('content_urls',{}).get('desktop',{}).get('page')
                    if data.get('type')=='disambiguation':continue
                    if url and len(text)>40 and relevant(query,title,text):
                        return {'answer':extract(query,text),'sources':[{'title':title,'url':url}], 'method':'extractive'}
            except Exception:
                continue
        return None
