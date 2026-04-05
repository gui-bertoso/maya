import json
import re
import ssl
import urllib.parse
import urllib.request
import webbrowser


class WebAssistant:
    def __init__(self):
        self.google_search_base = "https://www.google.com/search?q={query}"
        self.google_images_base = "https://www.google.com/search?tbm=isch&q={query}"
        self.youtube_search_base = "https://www.youtube.com/results?search_query={query}"
        self.youtube_music_search_base = "https://music.youtube.com/search?q={query}"
        self.common_sites = {
            "instagram": "instagram.com",
            "github": "github.com",
            "youtube": "youtube.com",
            "gmail": "mail.google.com",
            "google": "google.com",
            "twitter": "x.com",
            "x": "x.com",
            "reddit": "reddit.com",
            "twitch": "twitch.tv",
            "netflix": "netflix.com",
            "spotify": "open.spotify.com",
        }
        self.request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        }

    @staticmethod
    def _encode(value):
        return urllib.parse.quote_plus(value.strip())

    @staticmethod
    def _trim_summary(text, max_sentences=2, max_length=260):
        if not text:
            return None

        pieces = re.split(r"(?<=[.!?])\s+", text.strip())
        summary = " ".join(piece for piece in pieces[:max_sentences] if piece).strip()

        if len(summary) > max_length:
            summary = summary[: max_length - 3].rstrip() + "..."

        return summary or None

    @staticmethod
    def _clean_fragment(text):
        return re.sub(r"\s+", " ", (text or "").strip())

    @staticmethod
    def _strip_leading_article(term):
        return re.sub(r"^(?:a|an|the)\s+", "", term.strip(), flags=re.IGNORECASE)

    @staticmethod
    def _extract_translate_request(query):
        patterns = [
            r'^translate\s+"?([^"]+?)"?\s+to\s+([a-zA-Z ]+)$',
            r"^how translate\s+\"?([^\"]+?)\"?\s+to\s+([a-zA-Z ]+)$",
            r"^how do you say\s+\"?([^\"]+?)\"?\s+in\s+([a-zA-Z ]+)$",
            r"^how is\s+\"?([^\"]+?)\"?\s+in\s+([a-zA-Z ]+)$",
            r"^what is\s+\"?([^\"]+?)\"?\s+in\s+([a-zA-Z ]+)$",
            r"^what's\s+\"?([^\"]+?)\"?\s+in\s+([a-zA-Z ]+)$",
        ]

        for pattern in patterns:
            match = re.match(pattern, query.strip().lower())
            if match:
                term = match.group(1).strip()
                language = match.group(2).strip()
                if term and language:
                    return term, language
        return None

    @staticmethod
    def _extract_define_request(query):
        patterns = [
            r"^define\s+(.+)$",
            r"^what is\s+(.+)$",
            r"^what's\s+(.+)$",
            r"^whats\s+(.+)$",
            r"^meaning of\s+(.+)$",
        ]

        lowered = query.strip().lower()
        for pattern in patterns:
            match = re.match(pattern, lowered)
            if match:
                term = match.group(1).strip(" .!?\"'")
                if term:
                    return term
        return None

    def _open_request(self, url):
        request = urllib.request.Request(url, headers=self.request_headers)

        try:
            return urllib.request.urlopen(request, timeout=6)
        except ssl.SSLError:
            insecure_context = ssl._create_unverified_context()
            return urllib.request.urlopen(request, timeout=6, context=insecure_context)

    def _fetch_json(self, url):
        with self._open_request(url) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)

    def open_url(self, url):
        webbrowser.open(url)

    def open_web_search(self, query):
        self.open_url(self.build_web_search_url(query))

    def open_image_search(self, query):
        self.open_url(self.build_image_search_url(query))

    def open_video_search(self, query):
        self.open_url(self.build_video_search_url(query))

    def open_site(self, site_target):
        self.open_url(self.build_site_url(site_target))

    def build_web_search_url(self, query):
        return self.google_search_base.format(query=self._encode(query))

    def build_image_search_url(self, query):
        return self.google_images_base.format(query=self._encode(query))

    def build_video_search_url(self, query):
        return self.youtube_search_base.format(query=self._encode(query))

    def build_youtube_music_search_url(self, query):
        return self.youtube_music_search_base.format(query=self._encode(query))

    def build_site_url(self, site_target):
        target = site_target.strip().lower()
        if target in self.common_sites:
            target = self.common_sites[target]
        elif "." not in target and re.match(r"^[a-z0-9-]+$", target):
            target = f"www.{target}.com"
        if not re.match(r"^https?://", target):
            target = "https://" + target
        return target

    def get_text_summary(self, query):
        translation = self._try_translation(query)
        if translation:
            return translation

        definition = self._try_definition(query)
        if definition:
            return definition

        summary = self._try_duckduckgo_summary(query)
        if summary:
            return summary

        return self._try_wikipedia_summary(query)

    def _try_spelling_suggestion(self, term):
        url = f"https://api.datamuse.com/sug?s={self._encode(term)}&max=1"

        try:
            data = self._fetch_json(url)
        except Exception:
            return None

        if not isinstance(data, list) or not data:
            return None

        suggestion = self._clean_fragment(data[0].get("word", ""))
        if not suggestion:
            return None

        return suggestion

    def _try_translation(self, query):
        parsed = self._extract_translate_request(query)
        if not parsed:
            return None

        term, target_language = parsed
        url = (
            "https://api.mymemory.translated.net/get"
            f"?q={self._encode(term)}&langpair=en|{self._encode(target_language)}"
        )

        try:
            data = self._fetch_json(url)
        except Exception:
            return None

        response_data = data.get("responseData", {})
        translated_text = self._clean_fragment(response_data.get("translatedText", ""))

        if not translated_text or translated_text.lower() == term.lower():
            matches = data.get("matches", [])
            for match in matches:
                candidate = self._clean_fragment(match.get("translation", ""))
                if candidate and candidate.lower() != term.lower():
                    translated_text = candidate
                    break

        if not translated_text:
            return None

        return f"{term} in {target_language} is {translated_text}."

    def _try_definition(self, query):
        term = self._extract_define_request(query)
        if not term:
            return None

        candidates = []
        stripped_term = self._strip_leading_article(term)

        for candidate in [term, stripped_term]:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        suggestion = self._try_spelling_suggestion(stripped_term)
        if suggestion and suggestion not in candidates:
            candidates.append(suggestion)

        for candidate in candidates:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{self._encode(candidate)}"

            try:
                data = self._fetch_json(url)
            except Exception:
                continue

            if not isinstance(data, list) or not data:
                continue

            for entry in data:
                word = self._clean_fragment(entry.get("word", "")) or candidate
                meanings = entry.get("meanings", [])
                for meaning in meanings:
                    part_of_speech = meaning.get("partOfSpeech", "")
                    definitions = meaning.get("definitions", [])
                    for definition in definitions:
                        text = self._clean_fragment(definition.get("definition", ""))
                        if text:
                            prefix = f"{word} ({part_of_speech})" if part_of_speech else word
                            return self._trim_summary(f"{prefix}: {text}", max_sentences=1, max_length=220)

        return None

    def _try_duckduckgo_summary(self, query):
        url = (
            "https://api.duckduckgo.com/"
            f"?q={self._encode(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        )

        try:
            data = self._fetch_json(url)
        except Exception:
            return None

        abstract = data.get("AbstractText") or ""
        if abstract:
            return self._trim_summary(abstract)

        related_topics = data.get("RelatedTopics") or []
        for item in related_topics:
            if isinstance(item, dict) and item.get("Text"):
                return self._trim_summary(item["Text"])

        return None

    def _try_wikipedia_summary(self, query):
        search_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=opensearch&search={self._encode(query)}&limit=1&namespace=0&format=json"
        )

        try:
            search_result = self._fetch_json(search_url)
            titles = search_result[1] if isinstance(search_result, list) and len(search_result) > 1 else []
            if not titles:
                return None

            title = titles[0]
            summary_url = (
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                f"{urllib.parse.quote(title)}"
            )
            summary_result = self._fetch_json(summary_url)
        except Exception:
            return None

        extract = summary_result.get("extract") or ""
        return self._trim_summary(extract)
