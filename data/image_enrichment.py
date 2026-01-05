"""
Enriquecimento de HTML com imagens de APIs gratuitas.
Extrai keywords das respostas LLM e injeta imagens ilustrativas.
"""

import re
import urllib.request
import urllib.parse
import urllib.error
import time
import os
import json
from functools import lru_cache
from typing import Optional

# APIs de imagens gratuitas (sem necessidade de API key)
IMAGE_PROVIDERS = {
    'wikimedia': {
        'name': 'Wikimedia Commons',
        'description': 'Imagens da Wikipedia (pesquisa por keywords)',
        'url_template': None  # Uses search API
    },
    'openverse': {
        'name': 'Openverse',
        'description': 'Imagens CC via Openverse (pesquisa por keywords)',
        'url_template': None  # Uses search API
    },
    'pexels': {
        'name': 'Pexels',
        'description': 'Imagens do Pexels (requer PEXELS_API_KEY)',
        'url_template': None  # Uses search API
    },
    'unsplash': {
        'name': 'Unsplash Source',
        'description': 'Imagens de alta qualidade (pode ter 503 - instável)',
        'url_template': 'https://source.unsplash.com/300/200/?{keywords}'
    },
    'radiopaedia': {
        'name': 'Radiopaedia',
        'description': 'Casos radiológicos (scraping; devolve 1 imagem representativa por caso)',
        'url_template': None
    },
    'none': {
        'name': 'Sem imagens',
        'description': 'Não adicionar imagens automaticamente',
        'url_template': None
    }
}


# ---- Optional in-memory prefetch (no files, no data URIs) ----
_PREFETCH_CACHE: dict[str, bytes] = {}
_PREFETCH_CACHE_MAX = 256


_UA = 'GiftTest/1.0 (educational app)'


_HTML_HEADERS = {
    'User-Agent': _UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _http_get_text(url: str, timeout: int = 15, headers: Optional[dict] = None) -> str:
    if not url:
        return ''
    h = headers or _HTML_HEADERS
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')


def _absolutize_url(base: str, href: str) -> str:
    if not href:
        return ''
    return urllib.parse.urljoin(base, href)


@lru_cache(maxsize=200)
def _radiopaedia_search_case_urls(term: str, limit: int = 12) -> tuple[str, ...]:
    """Return Radiopaedia case URLs for a term by scraping the public search page.

    Notes:
    - Radiopaedia does not expose a simple public JSON search API for anonymous use.
    - We keep this lightweight: fetch HTML and extract /cases/<slug> links.
    """
    term = (term or '').strip()
    if not term:
        return tuple()

    q = urllib.parse.quote(term)
    # Radiopaedia uses `q=` for the search term.
    search_url = f'https://radiopaedia.org/search?lang=gb&scope=cases&q={q}'
    try:
        html = _http_get_text(search_url, timeout=15)
    except Exception:
        return tuple()

    # Extract case links; ignore system browsing links.
    hrefs = re.findall(r'href="(/cases/[^"?#]+)', html, flags=re.IGNORECASE)
    out: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        if not href.startswith('/cases/'):
            continue
        if href.startswith('/cases/system/'):
            continue
        # Skip non-content routes.
        if href in {'/cases/new'}:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(_absolutize_url('https://radiopaedia.org', href) + '?lang=gb')
        if len(out) >= int(limit):
            break
    return tuple(out)


@lru_cache(maxsize=400)
def _radiopaedia_case_og_image(case_url: str) -> str:
    """Return a representative image URL for a Radiopaedia case page.

    We prefer the `og:image` meta tag (typically a stable gallery/preview JPG).
    """
    url = (case_url or '').strip()
    if not url:
        return ''
    try:
        html = _http_get_text(url, timeout=15)
    except Exception:
        return ''

    m = re.search(
        r'<meta\s+property="og:image"\s+content="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if m:
        candidate = (m.group(1) or '').strip()
        # Ignore site assets/logos; we want an actual case image.
        if candidate and 'prod-images-static.radiopaedia.org/' in candidate:
            return candidate

    # Fallback: any embedded prod-images-static URL.
    m2 = re.search(r'https://prod-images-static\.radiopaedia\.org/[^"\s>]+\.(?:jpg|jpeg|png)', html, flags=re.IGNORECASE)
    return (m2.group(0) or '').strip() if m2 else ''


@lru_cache(maxsize=200)
def search_radiopaedia_images(keywords: str, max_results: int = 3) -> tuple[tuple[str, str], ...]:
    """Search Radiopaedia cases and return (image_url, landing_case_url).

    This is best-effort scraping (no auth). It purposely fetches only a handful of
    case pages to keep it reasonably fast.
    """
    clean = re.sub(r'[^\w\s,\-]', ' ', keywords or '')
    search_term = re.sub(r'\s+', ' ', clean.replace(',', ' ')).strip()
    if not search_term:
        return tuple()

    def _collect(term: str, needed: int) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        for case_url in _radiopaedia_search_case_urls(term, limit=max(12, needed * 6)):
            img = _radiopaedia_case_og_image(case_url)
            if not img:
                continue
            results.append((img, case_url))
            if len(results) >= needed:
                break
        return results

    try:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()

        for img, landing in _collect(search_term, max_results):
            k = f'{img}|{landing}'
            if k in seen:
                continue
            seen.add(k)
            out.append((img, landing))
        if len(out) >= max_results:
            return tuple(out)

        parts = [p.strip() for p in (keywords or '').split(',') if p.strip()]
        if len(parts) <= 1:
            return tuple(out)

        for p in parts:
            if len(out) >= max_results:
                break
            term = re.sub(r'\s+', ' ', re.sub(r'[^\w\s\-]', ' ', p)).strip()
            if not term:
                continue
            for img, landing in _collect(term, max_results - len(out)):
                k = f'{img}|{landing}'
                if k in seen:
                    continue
                seen.add(k)
                out.append((img, landing))
                if len(out) >= max_results:
                    break

        return tuple(out)
    except Exception:
        return tuple()


def get_prefetched_image_bytes(url: str) -> Optional[bytes]:
    """Returns prefetched bytes for an image URL, if available."""
    if not url:
        return None
    return _PREFETCH_CACHE.get(url)


def _put_prefetched_image_bytes(url: str, data: bytes) -> None:
    if not url or not data:
        return
    # Simple capped dict (FIFO-ish by insertion order in Py3.7+)
    if url in _PREFETCH_CACHE:
        return
    _PREFETCH_CACHE[url] = data
    if len(_PREFETCH_CACHE) > _PREFETCH_CACHE_MAX:
        try:
            oldest_key = next(iter(_PREFETCH_CACHE.keys()))
            _PREFETCH_CACHE.pop(oldest_key, None)
        except Exception:
            _PREFETCH_CACHE.clear()


def _media_fragment_url(file_page_url: str) -> str:
    """Converte uma página de ficheiro da Wikipedia/Commons para o fragmento #/media."""
    if not file_page_url:
        return file_page_url
    if '#/media/' in file_page_url:
        return file_page_url

    if 'pt.wikipedia.org/wiki/Ficheiro:' in file_page_url:
        title = file_page_url.split('pt.wikipedia.org/wiki/', 1)[1]
        return f"{file_page_url}#/media/{title}"
    if 'en.wikipedia.org/wiki/File:' in file_page_url:
        title = file_page_url.split('en.wikipedia.org/wiki/', 1)[1]
        return f"{file_page_url}#/media/{title}"
    if 'commons.wikimedia.org/wiki/File:' in file_page_url:
        title = file_page_url.split('commons.wikimedia.org/wiki/', 1)[1]
        return f"{file_page_url}#/media/{title}"

    return file_page_url


def _safe_html_comment_text(s: str) -> str:
    """Ensure we don't emit invalid HTML comments (no `--` inside)."""
    if s is None:
        return ''
    # HTML comments cannot contain `--`.
    return str(s).replace('--', '- -')


def _build_url_with_query(base_url: str, params: dict) -> str:
    query = urllib.parse.urlencode(params)
    return f"{base_url}?{query}" if query else base_url


def _commons_api_get_json(params: dict, timeout: int = 10) -> dict:
    import json

    url = _build_url_with_query('https://commons.wikimedia.org/w/api.php', params)
    req = urllib.request.Request(url)
    req.add_header('User-Agent', _UA)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _commons_search_titles(srsearch: str, limit: int) -> list[str]:
    data = _commons_api_get_json(
        {
            'action': 'query',
            'list': 'search',
            'srnamespace': 6,
            'srlimit': int(limit),
            'srsort': 'relevance',
            'format': 'json',
            'srsearch': srsearch,
        },
        timeout=10,
    )
    titles: list[str] = []
    for result in (data.get('query', {}).get('search', []) or []):
        title = (result.get('title') or '').strip()
        if not title:
            continue
        if not any(title.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg']):
            continue
        titles.append(title)
    return titles


def _commons_imageinfo_thumbs(titles: list[str], width: int) -> dict[str, str]:
    """Batch-fetch thumbnail URLs for multiple File: titles in one request."""
    if not titles:
        return {}

    joined = '|'.join(titles)
    data = _commons_api_get_json(
        {
            'action': 'query',
            'prop': 'imageinfo',
            'iiprop': 'url',
            'format': 'json',
            'iiurlwidth': int(width),
            'redirects': 1,
            'titles': joined,
        },
        timeout=10,
    )

    out: dict[str, str] = {}
    pages = (data.get('query', {}) or {}).get('pages', {}) or {}
    for page in pages.values():
        title = (page.get('title') or '').strip()
        if not title:
            continue
        imageinfo = (page.get('imageinfo') or [{}])
        ii = imageinfo[0] if imageinfo else {}
        if not isinstance(ii, dict):
            continue
        url = (ii.get('thumburl') or ii.get('url') or '').strip()
        if url:
            out[title] = url
    return out


def _build_commons_cirrus_query(clean_keywords: str, search_term: str) -> str:
    """Build a Wikimedia Commons CirrusSearch query.

    NOTE: Commons' `list=search` API supports searching captions via the
    CirrusSearch `incaption:` keyword. However, combining `incaption:` with
    boolean operators (e.g. `OR`) can be unreliable and can yield 0 hits for
    otherwise-valid queries.

    For caption search we therefore run a separate query using `incaption:` and
    merge results in code.
    """
    term = re.sub(r'\s+', ' ', (search_term or '').strip())
    return term


def _normalize_openverse_term(raw: str) -> str:
    clean = re.sub(r'[^\w\sáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', ' ', raw or '')
    term = re.sub(r'\s+', ' ', clean).strip()
    if not term:
        return ''
    import unicodedata
    term = ''.join(
        c for c in unicodedata.normalize('NFKD', term)
        if not unicodedata.combining(c)
    )
    return term


def _get_pexels_api_key() -> str:
    """Returns a Pexels API key from env, or from the app preferences JSON if present."""
    key = (os.environ.get('PEXELS_API_KEY') or os.environ.get('PEXELS_API_TOKEN') or '').strip()
    if key:
        return key

    # Best-effort: read from preferences.json (legacy or per-user path)
    try:
        from .app_paths import get_preferences_path
        candidates = [
            get_preferences_path(),
            os.path.join('data', 'preferences.json'),
        ]
        for p in candidates:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                val = (prefs.get('llm', {}).get('api_keys', {}) or {}).get('pexels', '')
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                continue
    except Exception:
        pass

    return ''


def _build_right_image_block(image_url: str, link_url: str, alt_text: str = "", processed: bool = True) -> str:
    """Cria um mini-bloco alinhado à direita, sem quebrar o texto."""
    link_url = _media_fragment_url(link_url)
    processed_attr = ' data-processed="true"' if processed else ''
    safe_alt = alt_text or ''
    # Nota: em QTextBrowser, floats funcionam, mas múltiplos floats podem ficar instáveis.
    # `clear: right` força cada bloco a empilhar na direita, evitando que os seguintes
    # acabem num layout centrado com whitespace.
    return (
        f'<span style="float: right; clear: right; width: 4em; height: 3.2em; overflow: hidden; '
        f'margin: 0 0 0.2em 0.5em; text-align: center;">'
        f'<a href="{link_url}" title="{safe_alt}" style="text-decoration: none;">'
        f'<img src="{image_url}" alt="{safe_alt}"{processed_attr} '
        f'style="display: block; max-width: 4em; max-height: 3.2em; height: auto; width: auto; margin: 0 auto; border: 1px solid #ccc;"/>'
        f'</a>'
        f'</span>'
    )


@lru_cache(maxsize=100)
def search_wikimedia_image(keywords: str) -> Optional[str]:
    """Pesquisa imagem na Wikimedia Commons usando a API.
    
    Args:
        keywords: Palavras-chave para pesquisa
        
    Returns:
        URL direta da imagem ou None se não encontrar
    """
    import json
    
    # Limpa keywords
    clean_keywords = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', '', keywords)
    search_term = clean_keywords.replace(',', ' ').strip()
    
    if not search_term:
        return None
    
    def _query_commons_titles(term: str) -> list[str]:
        """Search files by text; if needed, also search captions via `incaption:`."""
        q = _build_commons_cirrus_query(clean_keywords, term)
        if not q:
            return []

        primary = _commons_search_titles(q, limit=5)
        if primary:
            return primary

        phrase = q.replace('"', '').strip()
        if not phrase:
            return []
        return _commons_search_titles(f'incaption:"{phrase}"', limit=5)

    try:
        # First: try full query as-is (commas -> spaces)
        titles = _query_commons_titles(search_term)
        if titles:
            thumbs = _commons_imageinfo_thumbs(titles[:5], width=300)
            for title in titles:
                image_url = thumbs.get(title)
                if image_url:
                    return image_url

        # Fallback: query each comma-separated group separately
        parts = [p.strip() for p in (clean_keywords or '').split(',') if p.strip()]
        if len(parts) <= 1:
            return None
        for p in parts:
            titles = _query_commons_titles(p)
            if not titles:
                continue
            thumbs = _commons_imageinfo_thumbs(titles[:5], width=300)
            for title in titles:
                image_url = thumbs.get(title)
                if image_url:
                    return image_url

        return None
    except Exception:
        return None


@lru_cache(maxsize=200)
def search_wikimedia_images(keywords: str, max_results: int = 3, thumb_width: int = 160) -> tuple[tuple[str, str], ...]:
    """Pesquisa até `max_results` imagens na Wikimedia Commons.

    Returns:
        Tuplos (thumb_url, media_url) por ordem de relevância.
    """
    import json

    clean_keywords = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', '', keywords)
    search_term = clean_keywords.replace(',', ' ').strip()
    if not search_term:
        return tuple()

    def _query_commons_titles(term: str, limit: int = 10) -> list[str]:
        """Run plain search first; use `incaption:` only if needed to fill `limit`."""
        q = _build_commons_cirrus_query(clean_keywords, term)
        if not q:
            return []

        primary = _commons_search_titles(q, limit=int(limit))
        if len(primary) >= int(limit):
            return primary

        phrase = q.replace('"', '').strip()
        if not phrase:
            return primary

        caption = _commons_search_titles(f'incaption:"{phrase}"', limit=int(limit))

        merged: list[str] = []
        seen: set[str] = set()
        for t in primary + caption:
            if t in seen:
                continue
            seen.add(t)
            merged.append(t)
            if len(merged) >= int(limit):
                break
        return merged

    def _titles_to_results(titles: list[str], out: list[tuple[str, str]], seen: set[str]) -> None:
        if not titles or len(out) >= max_results:
            return

        thumbs = _commons_imageinfo_thumbs(titles, width=thumb_width)
        for title in titles:
            thumb = thumbs.get(title)
            if not thumb:
                continue
            file_page = f"https://commons.wikimedia.org/wiki/{title}"
            key = f'{thumb}|{file_page}'
            if key in seen:
                continue
            seen.add(key)
            out.append((thumb, file_page))
            if len(out) >= max_results:
                return

    try:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()

        # First: try full query as-is (commas -> spaces)
        _titles_to_results(_query_commons_titles(search_term, limit=10), out, seen)
        if len(out) >= max_results:
            return tuple(out)

        # Fallback: query each comma-separated group separately and merge
        parts = [p.strip() for p in (clean_keywords or '').split(',') if p.strip()]
        if len(parts) <= 1:
            return tuple(out)

        for p in parts:
            _titles_to_results(_query_commons_titles(p, limit=10), out, seen)
            if len(out) >= max_results:
                return tuple(out)

        return tuple(out)
    except Exception:
        return tuple()


@lru_cache(maxsize=200)
def search_openverse_images(keywords: str, max_results: int = 3) -> tuple[tuple[str, str], ...]:
    """Pesquisa até `max_results` imagens no Openverse.

    Returns:
        Tuplos (thumbnail_url, landing_url) por ordem de relevância.
    """
    import json

    def _query_openverse(term: str) -> tuple[tuple[str, str], ...]:
        if not term:
            return tuple()
        query = urllib.parse.urlencode(
            {
                'q': term,
                'page_size': 20,
                'mature': 'false',
            }
        )
        api_url = f'https://api.openverse.org/v1/images/?{query}'
        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', 'GiftTest/1.0 (educational app)')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        results = data.get('results', []) or []
        out: list[tuple[str, str]] = []
        for r in results:
            thumb = r.get('thumbnail') or r.get('thumbnail_url') or ''
            landing = r.get('foreign_landing_url') or r.get('detail_url') or r.get('url') or ''
            if not thumb or not landing:
                continue
            out.append((thumb, landing))
            if len(out) >= max_results:
                break
        return tuple(out)

    try:
        # First: try the full query as-is (commas -> spaces)
        normalized_full = _normalize_openverse_term((keywords or '').replace(',', ' '))
        primary = _query_openverse(normalized_full)
        if primary:
            return primary

        # Fallback: if the keywords contain comma-separated terms, query each term separately
        parts = [p.strip() for p in (keywords or '').split(',') if p.strip()]
        if len(parts) <= 1:
            return tuple()

        seen: set[str] = set()
        merged: list[tuple[str, str]] = []
        for p in parts:
            term = _normalize_openverse_term(p)
            for thumb, landing in _query_openverse(term):
                key = f'{thumb}|{landing}'
                if key in seen:
                    continue
                seen.add(key)
                merged.append((thumb, landing))
                if len(merged) >= max_results:
                    return tuple(merged)

        return tuple(merged)
    except Exception:
        return tuple()


@lru_cache(maxsize=200)
def search_pexels_images(keywords: str, max_results: int = 3) -> tuple[tuple[str, str], ...]:
    """Search images on Pexels.

    Requires an API key via env var PEXELS_API_KEY (recommended) or preferences llm.api_keys.pexels.
    Returns:
        Tuples (thumbnail_url, landing_url).
    """
    api_key = _get_pexels_api_key()
    if not api_key:
        return tuple()

    clean = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', ' ', keywords or '')
    search_term = re.sub(r'\s+', ' ', clean.replace(',', ' ')).strip()
    if not search_term:
        return tuple()

    base_url = 'https://api.pexels.com/v1/search'
    params = {
        'query': search_term,
        'per_page': max(1, min(int(max_results) if max_results else 3, 15)),
    }
    url = _build_url_with_query(base_url, params)

    try:
        req = urllib.request.Request(url)
        req.add_header('Authorization', api_key)
        req.add_header('User-Agent', 'GiftTest/1.0 (educational app)')
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode('utf-8'))

        photos = data.get('photos', []) or []
        out: list[tuple[str, str]] = []
        for p in photos:
            landing = p.get('url') or ''
            src = p.get('src') or {}
            thumb = src.get('medium') or src.get('small') or src.get('tiny') or src.get('original') or ''
            if not thumb or not landing:
                continue
            out.append((thumb, landing))
            if len(out) >= max_results:
                break
        return tuple(out)
    except Exception:
        return tuple()


@lru_cache(maxsize=100)
def get_wikimedia_image_url(file_title: str, width: int = 300) -> Optional[str]:
    """Obtém URL direta de uma imagem da Wikimedia Commons.
    
    Args:
        file_title: Título do ficheiro (ex: 'File:Example.jpg')
        width: Largura desejada em pixels
        
    Returns:
        URL direta da imagem redimensionada
    """
    import json
    
    # API para obter informação da imagem
    api_url = (
        'https://commons.wikimedia.org/w/api.php?'
        'action=query&prop=imageinfo&iiprop=url&format=json&'
        f'iiurlwidth={width}&titles={urllib.parse.quote(file_title)}'
    )
    
    try:
        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', _UA)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            imageinfo = page.get('imageinfo', [{}])[0]
            # Prefere versão redimensionada (thumburl), senão usa original
            return imageinfo.get('thumburl') or imageinfo.get('url')
        
        return None
    except Exception:
        return None


@lru_cache(maxsize=100)
def build_image_url(provider: str, keywords: str) -> Optional[str]:
    """Constrói URL de imagem baseado no provider e keywords.
    
    Args:
        provider: Nome do provider ('wikimedia', 'openverse', 'unsplash', 'none')
        keywords: Palavras-chave separadas por vírgula ou espaço
        
    Returns:
        URL da imagem ou None se provider='none' ou 'placeholder'
    """
    if provider not in IMAGE_PROVIDERS:
        return None
    
    # Wikimedia usa pesquisa especial
    if provider == 'wikimedia':
        return search_wikimedia_image(keywords)

    # Openverse usa pesquisa especial
    if provider == 'openverse':
        images = search_openverse_images(keywords, max_results=1)
        return images[0][0] if images else None

    # Pexels usa pesquisa especial
    if provider == 'pexels':
        images = search_pexels_images(keywords, max_results=1)
        return images[0][0] if images else None
    
    template = IMAGE_PROVIDERS[provider].get('url_template')
    if not template:
        return None
    
    # Limpa e formata keywords
    clean_keywords = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', '', keywords)
    clean_keywords = clean_keywords.strip()
    
    if '{keywords}' in template:
        # Para Unsplash: substitui espaços e vírgulas por vírgulas
        formatted = clean_keywords.replace(' ', ',').replace(',,', ',')
        encoded = urllib.parse.quote(formatted)
        return template.format(keywords=encoded)
    
    # Para providers sem keywords (ex: picsum) - retorna URL diretamente
    return template


def extract_image_keywords_from_html(html: str) -> Optional[str]:
    """Extrai keywords para busca de imagem do HTML.
    
    Procura por um comentário especial no formato:
    <!-- IMAGE_KEYWORDS: palavra1, palavra2, palavra3 -->
    
    Args:
        html: Conteúdo HTML da resposta LLM
        
    Returns:
        String com keywords ou None se não encontrado
    """
    pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        keywords = match.group(1).strip()
        keywords = re.sub(r'[\n\r\t]+', ' ', keywords).strip()
        return keywords
    return None


def extract_all_image_keywords_from_html(html: str) -> list[str]:
    """Extrai TODOS os comentários IMAGE_KEYWORDS na ordem em que aparecem."""
    pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'
    matches = re.findall(pattern, html, flags=re.IGNORECASE)
    out: list[str] = []
    for m in matches:
        keywords = (m or '').strip()
        keywords = re.sub(r'[\n\r\t]+', ' ', keywords).strip()
        if keywords:
            out.append(keywords)
    return out


def inject_image_into_html(html: str, image_url: str, alt_text: str = "") -> str:
    """Injeta uma tag de imagem no HTML.
    
    A imagem é inserida no início do conteúdo, antes de qualquer texto.
    Usa data-processed="true" para evitar reprocessamento.
    
    Args:
        html: Conteúdo HTML original
        image_url: URL da imagem
        alt_text: Texto alternativo para a imagem
        
    Returns:
        HTML com imagem injetada
    """
    # Calcula URL da página de media
    media_url = image_url
    if 'wikimedia.org' in image_url:
        match = re.search(r'/(?:thumb/)?[a-f0-9]/[a-f0-9]{2}/([^/]+?)(?:/\d+px-[^/]+)?$', image_url, re.IGNORECASE)
        if match:
            filename = match.group(1)
            if '/wikipedia/commons/' in image_url:
                media_url = f'https://commons.wikimedia.org/wiki/File:{filename}'
            elif '/wikipedia/pt/' in image_url:
                media_url = f'https://pt.wikipedia.org/wiki/Ficheiro:{filename}'
            else:
                media_url = f'https://commons.wikimedia.org/wiki/File:{filename}'

    img_tag = _build_right_image_block(image_url=image_url, link_url=media_url, alt_text=alt_text, processed=True)
    
    # Tenta inserir após primeiro h1 ou h2
    pattern = r'(<h[12][^>]*>.*?</h[12]>)'
    if re.search(pattern, html, re.IGNORECASE | re.DOTALL):
        return re.sub(
            pattern,
            rf'\1\n{img_tag}',
            html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL
        )
    
    # Se é um <pre>, insere antes
    pre_pattern = r'(<pre[^>]*>)'
    if re.search(pre_pattern, html, re.IGNORECASE):
        return re.sub(
            pre_pattern,
            rf'{img_tag}\n\1',
            html,
            count=1,
            flags=re.IGNORECASE
        )
    
    # Se não há cabeçalho, insere no início (após tags iniciais como <!DOCTYPE>, <html>, <body>)
    body_pattern = r'(<body[^>]*>)'
    if re.search(body_pattern, html, re.IGNORECASE):
        return re.sub(
            body_pattern,
            rf'\1\n{img_tag}',
            html,
            count=1,
            flags=re.IGNORECASE
        )
    
    # Fallback: insere no início absoluto
    return img_tag + '\n' + html


def is_html_content(text: str) -> bool:
    """Verifica se o texto contém tags HTML."""
    html_pattern = r'<\s*(html|body|div|p|pre|span|img|h[1-6]|ul|ol|li|strong|em|br|hr|table|tr|td|th|a)\b[^>]*>'
    return bool(re.search(html_pattern, text, re.IGNORECASE))


def text_to_html_preserving_image_keywords(text: str) -> str:
    """Converte texto puro em HTML (<pre>) preservando comentários IMAGE_KEYWORDS.

    Isto permite que o texto venha como plain-text (ex: Gemma) mas ainda assim
    use o protocolo `<!-- IMAGE_KEYWORDS: ... -->` para injetar imagens.
    """
    import html

    comment_pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'
    tokens: dict[str, str] = {}
    token_prefix = '__IMAGE_KEYWORDS_TOKEN_'
    counter = 0

    def _tokenize(match: re.Match) -> str:
        nonlocal counter
        token = f'{token_prefix}{counter}__'
        tokens[token] = match.group(0)
        counter += 1
        return token

    tokenized = re.sub(comment_pattern, _tokenize, text, flags=re.IGNORECASE)
    escaped = html.escape(tokenized)

    # Restaura os comentários (sem escape), para poderem ser processados depois.
    for token, comment in tokens.items():
        escaped = escaped.replace(html.escape(token), comment)

    return f'<pre style="white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6;">{escaped}</pre>'


def process_all_images(html: str) -> str:
    """Processa todas as tags <img> no HTML.
    
    - Adiciona link clicável a cada imagem (abre página de media da Wikipedia)
    - Redimensiona para 5x altura da linha (~80px)
    - Mantém inline com o texto
    - Corrige URLs da Wikimedia para usar thumbnails válidos
    
    Args:
        html: Conteúdo HTML
        
    Returns:
        HTML com todas as imagens processadas
    """
    def fix_wikimedia_url(url: str) -> str:
        """Corrige URLs de thumbnails da Wikimedia para tamanhos válidos."""
        # URLs como: .../thumb/.../800px-Filename.png -> .../thumb/.../300px-Filename.png
        # Wikimedia bloqueia pedidos com 429 para tamanhos não standard
        if 'wikimedia.org' in url and '/thumb/' in url:
            # Substitui qualquer tamanho por 300px (tamanho permitido)
            url = re.sub(r'/(\d+)px-', '/300px-', url)
        return url
    
    def get_media_page_url(url: str) -> str:
        """Converte URL de imagem para página de media da Wikipedia/Commons.
        
        De: https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/File.svg/300px-File.svg.png
        Para: https://commons.wikimedia.org/wiki/File:File.svg
        """
        if 'wikimedia.org' not in url:
            return url
        
        # Extrai nome do ficheiro da URL
        # Padrão: .../thumb/X/XX/Filename.ext/... ou .../X/XX/Filename.ext
        match = re.search(r'/(?:thumb/)?[a-f0-9]/[a-f0-9]{2}/([^/]+?)(?:/\d+px-[^/]+)?$', url, re.IGNORECASE)
        if match:
            filename = match.group(1)
            # Determina se é commons ou wikipedia
            if '/wikipedia/commons/' in url:
                return f'https://commons.wikimedia.org/wiki/File:{filename}'
            elif '/wikipedia/pt/' in url:
                return f'https://pt.wikipedia.org/wiki/Ficheiro:{filename}'
            elif '/wikipedia/en/' in url:
                return f'https://en.wikipedia.org/wiki/File:{filename}'
            else:
                # Fallback para commons
                return f'https://commons.wikimedia.org/wiki/File:{filename}'
        
        return url
    
    def replace_img(match):
        full_tag = match.group(0)
        
        # Ignora imagens já processadas (têm data-processed="true")
        if 'data-processed' in full_tag:
            return full_tag
        
        # Extrai src
        src_match = re.search(r'src=["\']([^"\']+)["\']', full_tag, re.IGNORECASE)
        if not src_match:
            return full_tag
        src = src_match.group(1)
        
        # Corrige URL da Wikimedia se necessário
        src = fix_wikimedia_url(src)
        
        # URL para a página de media (link clicável)
        media_url = get_media_page_url(src)
        
        # Se já está dentro de um <a>, não envolver novamente
        # Verifica contexto antes da tag
        start = match.start()
        context_before = html[max(0, start-50):start]
        if '<a ' in context_before.lower() and '</a>' not in context_before.lower():
            # Já está dentro de um link, só ajustar estilo e src
            new_tag = re.sub(r'style=["\'][^"\']*["\']', '', full_tag)
            new_tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{src}"', new_tag)
            new_tag = new_tag.replace('<img', 
                '<img style="display: inline-block; max-width: 4em; max-height: 3.2em; height: auto; width: auto; vertical-align: middle; border: 1px solid #ccc;"')
            return new_tag
        
        # Extrai alt se existir
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', full_tag, re.IGNORECASE)
        alt = alt_match.group(1) if alt_match else ''
        
        return _build_right_image_block(image_url=src, link_url=media_url, alt_text=alt, processed=False)
    
    # Processa todas as tags <img>
    result = re.sub(r'<img[^>]+/?>', replace_img, html, flags=re.IGNORECASE)
    return result


def text_to_html(text: str) -> str:
    """Converte texto puro em HTML, preservando formatação.
    
    Usa <pre> para manter quebras de linha e espaçamento exatamente
    como aparecem no texto original.
    """
    # Escape HTML se houver caracteres especiais
    import html
    escaped = html.escape(text)
    
    # Usa <pre> com wrap para preservar formatação mas permitir quebras
    return f'<pre style="white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6;">{escaped}</pre>'


def download_image(url: str, timeout: int = 10) -> Optional[bytes]:
    """Baixa uma imagem de uma URL.
    
    Args:
        url: URL da imagem
        timeout: Timeout em segundos
        
    Returns:
        Bytes da imagem ou None se falhar
    """
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            return data
    except Exception:
        return None


def get_placeholder_image() -> bytes:
    """Retorna uma pequena imagem placeholder PNG (quadrado cinza 100x100)."""
    import base64
    # PNG cinza 100x100 (~200 bytes)
    b64_data = """
iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAAXklEQVR42u3BMQEAAADCoPVPbQwf
oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD4
MwAFAAH3b5RnAAAAAElFTkSuQmCC
"""
    return base64.b64decode(b64_data.strip())


def enrich_html_with_image(content: str, provider: str, default_keywords: str = "") -> str:
    """Enriquece conteúdo com imagem se provider ativo e keywords disponíveis.
    
    Args:
        content: Conteúdo da resposta LLM (HTML ou texto puro)
        provider: Provider de imagens ('wikimedia', 'picsum', 'unsplash', 'placeholder', 'none')
        default_keywords: Keywords padrão se não encontrados no conteúdo
        
    Returns:
        HTML enriquecido com tag <img> (URL direta - QTextBrowser carrega via loadResource)
    """
    if provider == 'none':
        # Se não é HTML, converte
        if not is_html_content(content):
            return text_to_html_preserving_image_keywords(content)
        # Mesmo com provider=none, processa imagens existentes do LLM
        return process_all_images(content)

    # Converte texto para HTML se necessário (para preservar formatação no texto puro)
    if not is_html_content(content):
        content = text_to_html_preserving_image_keywords(content)

    # Substitui cada comentário IMAGE_KEYWORDS por até 3 imagens relevantes
    comment_pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'

    def _replace_comment(match: re.Match) -> str:
        raw_keywords = (match.group(1) or '').strip()
        keywords = re.sub(r'[\n\r\t]+', ' ', raw_keywords).strip()
        if not keywords:
            return ''

        blocks: list[str] = []
        if provider == 'wikimedia':
            images = search_wikimedia_images(keywords, max_results=3, thumb_width=160)
            for thumb_url, file_page_url in images:
                blocks.append(_build_right_image_block(image_url=thumb_url, link_url=file_page_url, alt_text=keywords, processed=True))
        elif provider == 'openverse':
            images = search_openverse_images(keywords, max_results=3)
            for thumb_url, landing_url in images:
                blocks.append(_build_right_image_block(image_url=thumb_url, link_url=landing_url, alt_text=keywords, processed=True))
        else:
            image_url = build_image_url(provider, keywords)
            if image_url:
                blocks.append(_build_right_image_block(image_url=image_url, link_url=image_url, alt_text=keywords, processed=True))

        return ''.join(blocks)

    had_comments = bool(re.search(comment_pattern, content, flags=re.IGNORECASE))
    if had_comments:
        # Se o conteúdo estiver em <pre>, não inserir blocos (table) dentro do <pre>
        # porque o QTextBrowser tende a ignorar/partir este HTML. Em vez disso,
        # colocamos os blocos antes do primeiro <pre>.
        if re.search(r'<pre\b', content, flags=re.IGNORECASE):
            all_keywords = extract_all_image_keywords_from_html(content)
            content = re.sub(comment_pattern, '', content, flags=re.IGNORECASE)

            blocks: list[str] = []
            for keywords in all_keywords:
                if provider == 'wikimedia':
                    images = search_wikimedia_images(keywords, max_results=3, thumb_width=160)
                    for thumb_url, file_page_url in images:
                        blocks.append(
                            _build_right_image_block(
                                image_url=thumb_url,
                                link_url=file_page_url,
                                alt_text=keywords,
                                processed=True,
                            )
                        )
                else:
                    image_url = build_image_url(provider, keywords)
                    if image_url:
                        blocks.append(
                            _build_right_image_block(
                                image_url=image_url,
                                link_url=image_url,
                                alt_text=keywords,
                                processed=True,
                            )
                        )

            if blocks:
                content = re.sub(
                    r'(<pre[^>]*>)',
                    ''.join(blocks) + r'\1',
                    content,
                    count=1,
                    flags=re.IGNORECASE,
                )
        else:
            content = re.sub(comment_pattern, _replace_comment, content, flags=re.IGNORECASE)
    elif default_keywords:
        # Sem comentários explícitos: usa keywords default e injeta até 3 imagens
        if provider == 'wikimedia':
            images = search_wikimedia_images(default_keywords, max_results=3, thumb_width=160)
            blocks = [
                _build_right_image_block(image_url=thumb_url, link_url=file_page_url, alt_text=default_keywords, processed=True)
                for thumb_url, file_page_url in images
            ]
        elif provider == 'openverse':
            images = search_openverse_images(default_keywords, max_results=3)
            blocks = [
                _build_right_image_block(image_url=thumb_url, link_url=landing_url, alt_text=default_keywords, processed=True)
                for thumb_url, landing_url in images
            ]
        else:
            image_url = build_image_url(provider, default_keywords)
            blocks = [
                _build_right_image_block(image_url=image_url, link_url=image_url, alt_text=default_keywords, processed=True)
            ] if image_url else []

        if blocks:
            blocks_html = ''.join(blocks)
            # Inserção: depois de h1/h2 se existir; se for <pre>, antes do <pre>; senão no <body>.
            if re.search(r'(<h[12][^>]*>.*?</h[12]>)', content, re.IGNORECASE | re.DOTALL):
                content = re.sub(
                    r'(<h[12][^>]*>.*?</h[12]>)',
                    rf'\1\n{blocks_html}',
                    content,
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            elif re.search(r'<pre\b', content, re.IGNORECASE):
                content = re.sub(
                    r'(<pre[^>]*>)',
                    blocks_html + r'\1',
                    content,
                    count=1,
                    flags=re.IGNORECASE,
                )
            elif re.search(r'(<body[^>]*>)', content, re.IGNORECASE):
                content = re.sub(
                    r'(<body[^>]*>)',
                    rf'\1\n{blocks_html}',
                    content,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                content = blocks_html + '\n' + content

    # Sempre processa <img> existentes (por exemplo, imagens geradas pelo próprio LLM)
    return process_all_images(content)


def split_explanation_html_and_images(
        content: str,
        provider: str,
        max_images_per_block: int = 3,
        prefetch_thumbnails: bool = True,
        thumb_width: int = 320,
) -> tuple[str, str, float, int, tuple[str, ...]]:
    """Splits an explanation into (text_html, images_column_html, images_time_seconds).

    New UX:
    - If there are no IMAGE_KEYWORDS comments, images_column_html is empty.
    - For each IMAGE_KEYWORDS block, we inject a numbered reference [i] into the text.
    - The images column contains groups labeled with the same [i], then the images + clickable link.
    """

    # Ensure HTML so that we can safely inject <sup> references.
    if not is_html_content(content):
        text_html = text_to_html_preserving_image_keywords(content)
    else:
        text_html = content

    comment_pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'
    matches = re.findall(comment_pattern, text_html, flags=re.IGNORECASE)
    keywords_list: list[str] = []
    for m in matches:
        kw = re.sub(r'[\n\r\t]+', ' ', (m or '')).strip()
        if kw:
            keywords_list.append(kw)

    if not keywords_list:
        # Remove the comments from the visible output (keep text clean)
        cleaned = re.sub(comment_pattern, '', text_html, flags=re.IGNORECASE)
        return cleaned, '', 0.0, 0, tuple()

    # Replace each comment with a visible counter reference in the text.
    counter = {'i': 0}

    def _replace_comment_with_ref(match: re.Match) -> str:
        raw_keywords = (match.group(1) or '').strip()
        kw = re.sub(r'[\n\r\t]+', ' ', raw_keywords).strip()
        if not kw:
            return ''
        counter['i'] += 1
        i = counter['i']
        return f'<sup>[{i}]</sup>'

    text_html = re.sub(comment_pattern, _replace_comment_with_ref, text_html, flags=re.IGNORECASE)

    images_html, images_time = build_images_column_html(
        tuple(keywords_list),
        provider=provider,
        max_images_per_block=max_images_per_block,
        prefetch_thumbnails=prefetch_thumbnails,
        thumb_width=thumb_width,
    )

    return text_html, images_html, images_time, len(keywords_list), tuple(keywords_list)


def split_explanation_text_and_keywords(content: str) -> tuple[str, int, tuple[str, ...]]:
    """Returns (text_html_with_refs, num_blocks, keywords_list) without fetching images."""
    if not is_html_content(content):
        text_html = text_to_html_preserving_image_keywords(content)
    else:
        text_html = content

    comment_pattern = r'<!--\s*IMAGE_KEYWORDS:\s*([^-]+?)\s*-->'
    matches = re.findall(comment_pattern, text_html, flags=re.IGNORECASE)
    keywords_list: list[str] = []
    for m in matches:
        kw = re.sub(r'[\n\r\t]+', ' ', (m or '')).strip()
        if kw:
            keywords_list.append(kw)

    if not keywords_list:
        cleaned = re.sub(comment_pattern, '', text_html, flags=re.IGNORECASE)
        return cleaned, 0, tuple()

    counter = {'i': 0}

    def _replace_comment_with_ref(match: re.Match) -> str:
        raw_keywords = (match.group(1) or '').strip()
        kw = re.sub(r'[\n\r\t]+', ' ', raw_keywords).strip()
        if not kw:
            return ''
        counter['i'] += 1
        i = counter['i']
        return f'<sup>[{i}]</sup>'

    text_html = re.sub(comment_pattern, _replace_comment_with_ref, text_html, flags=re.IGNORECASE)
    return text_html, len(keywords_list), tuple(keywords_list)


def _format_alt_text_for_keywords(keywords: str) -> str:
    parts = [p.strip() for p in (keywords or '').split(',') if p.strip()]
    if not parts:
        return "Imagem para keywords"
    bracketed = ', '.join(f'[{p}]' for p in parts)
    return f"Imagem para keywords: {bracketed}"


def build_images_column_html(
        keywords_list: tuple[str, ...],
        provider: str,
        max_images_per_block: int = 3,
        prefetch_thumbnails: bool = True,
        thumb_width: int = 320,
    target_image_width_px: Optional[int] = None,
) -> tuple[str, float]:
    """Builds the right-side images column HTML for an ordered keywords list."""
    if not keywords_list:
        return '', 0.0

    # If user chose 'none', keep layout without images.
    if provider == 'none':
        return '', 0.0

    groups, images_time = fetch_image_groups(
        keywords_list,
        provider=provider,
        max_images_per_block=max_images_per_block,
        prefetch_thumbnails=prefetch_thumbnails,
        thumb_width=thumb_width,
    )
    html = build_images_column_html_from_groups(
        keywords_list,
        groups,
        target_image_width_px=target_image_width_px,
    )
    return html, images_time


def fetch_image_groups(
        keywords_list: tuple[str, ...],
        provider: str,
        max_images_per_block: int = 3,
    prefetch_thumbnails: bool = False,
        thumb_width: int = 320,
) -> tuple[tuple, float]:
    """Fetches image URLs for each keywords block.

    Returns:
        (groups, seconds) where groups is a tuple of (images, error, debug) per block:
        - images: tuple[(thumb_url, landing_url), ...]
        - error: '' on success, 'no_results' when empty, or an exception string
        - debug: dict with provider, request URL(s) and params (for view-source debugging)
    """
    if not keywords_list:
        return tuple(), 0.0

    if provider == 'none':
        return tuple(((tuple(), 'provider_none', {'provider': 'none', 'requests': [], 'params': {}}) for _ in keywords_list)), 0.0

    start = time.time()
    out: list[tuple[tuple[tuple[str, str], ...], str, dict]] = []
    thumbs_to_prefetch: list[str] = []

    for keywords in keywords_list:
        images: tuple[tuple[str, str], ...] = tuple()
        err = ''
        debug: dict = {}
        try:
            if provider == 'wikimedia':
                clean_keywords = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', '', keywords)
                search_term = clean_keywords.replace(',', ' ').strip()
                params = {
                    'action': 'query',
                    'list': 'search',
                    'srnamespace': 6,
                    'srlimit': 10,
                    'format': 'json',
                    'srsearch': search_term,
                }
                search_url = _build_url_with_query('https://commons.wikimedia.org/w/api.php', params)
                imageinfo_params = {
                    'action': 'query',
                    'prop': 'imageinfo',
                    'iiprop': 'url',
                    'format': 'json',
                    'iiurlwidth': int(thumb_width),
                    'titles': 'File:...',
                }
                imageinfo_url_template = _build_url_with_query('https://commons.wikimedia.org/w/api.php', imageinfo_params)
                debug = {
                    'provider': 'wikimedia',
                    'requests': [search_url, imageinfo_url_template],
                    'params': {
                        'search_term': search_term,
                        'max_images_per_block': int(max_images_per_block),
                        'thumb_width': int(thumb_width),
                    },
                }
                images = search_wikimedia_images(keywords, max_results=max_images_per_block, thumb_width=thumb_width)
            elif provider == 'openverse':
                normalized_full = _normalize_openverse_term((keywords or '').replace(',', ' '))
                reqs = []
                if normalized_full:
                    reqs.append(
                        _build_url_with_query(
                            'https://api.openverse.org/v1/images/',
                            {'q': normalized_full, 'page_size': 20, 'mature': 'false'},
                        )
                    )
                parts = [p.strip() for p in (keywords or '').split(',') if p.strip()]
                if len(parts) > 1:
                    for p in parts:
                        term = _normalize_openverse_term(p)
                        if term:
                            reqs.append(
                                _build_url_with_query(
                                    'https://api.openverse.org/v1/images/',
                                    {'q': term, 'page_size': 20, 'mature': 'false'},
                                )
                            )
                debug = {
                    'provider': 'openverse',
                    'requests': reqs,
                    'params': {
                        'normalized_full': normalized_full,
                        'max_images_per_block': int(max_images_per_block),
                    },
                }
                images = search_openverse_images(keywords, max_results=max_images_per_block)
            elif provider == 'radiopaedia':
                clean = re.sub(r'[^\w\s,\-]', ' ', keywords or '')
                search_term = re.sub(r'\s+', ' ', clean.replace(',', ' ')).strip()
                reqs = []
                if search_term:
                    reqs.append(
                        _build_url_with_query(
                            'https://radiopaedia.org/search',
                            {'lang': 'gb', 'scope': 'cases', 'q': search_term},
                        )
                    )
                debug = {
                    'provider': 'radiopaedia',
                    'requests': reqs,
                    'params': {
                        'search_term': search_term,
                        'max_images_per_block': int(max_images_per_block),
                    },
                }
                images = search_radiopaedia_images(keywords, max_results=max_images_per_block)
            elif provider == 'pexels':
                clean = re.sub(r'[^\w\s,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ-]', ' ', keywords or '')
                search_term = re.sub(r'\s+', ' ', clean.replace(',', ' ')).strip()
                params = {
                    'query': search_term,
                    'per_page': max(1, min(int(max_images_per_block), 15)),
                }
                search_url = _build_url_with_query('https://api.pexels.com/v1/search', params)
                debug = {
                    'provider': 'pexels',
                    'requests': [search_url],
                    'params': {
                        **params,
                        'auth': 'Authorization: <PEXELS_API_KEY>',
                    },
                }
                images = search_pexels_images(keywords, max_results=max_images_per_block)
            else:
                image_url = build_image_url(provider, keywords)
                images = ((image_url, image_url),) if image_url else tuple()
                debug = {
                    'provider': provider,
                    'requests': [image_url] if image_url else [],
                    'params': {
                        'keywords': keywords,
                    },
                }
        except Exception as e:
            err = str(e)
            images = tuple()

        if not images and not err:
            err = 'no_results'

        out.append((images, err, debug))

        if prefetch_thumbnails and images:
            for thumb_url, _landing in images:
                if thumb_url:
                    thumbs_to_prefetch.append(thumb_url)

    if prefetch_thumbnails and thumbs_to_prefetch:
        # Cap and dedupe prefetch work to reduce latency (does not change results,
        # only improves perceived responsiveness).
        deduped: list[str] = []
        seen_u: set[str] = set()
        for u in thumbs_to_prefetch:
            if not u or u in seen_u:
                continue
            seen_u.add(u)
            deduped.append(u)

        for url in deduped[:12]:
            if not url or url in _PREFETCH_CACHE:
                continue
            data = download_image(url, timeout=3)
            if data:
                _put_prefetched_image_bytes(url, data)

    return tuple(out), (time.time() - start)


def build_images_column_html_from_groups(
        keywords_list: tuple[str, ...],
    groups: tuple,
        target_image_width_px: Optional[int] = None,
) -> str:
    """Builds HTML from already fetched groups (no network)."""
    if not keywords_list:
        return ''

    groups_html: list[str] = []
    width_attr = ''
    width_style = 'max-width:100%; height:auto;'
    if target_image_width_px and target_image_width_px > 0:
        # QTextBrowser handles numeric width reliably; % widths can be ignored.
        width_attr = f' width="{int(target_image_width_px)}"'
        width_style = f'width:{int(target_image_width_px)}px; height:auto;'

    html_lines: list[str] = []
    indent = '  '

    for idx, keywords in enumerate(keywords_list):
        i = idx + 1

        group = groups[idx] if idx < len(groups) else (tuple(), 'no_groups', {})
        if isinstance(group, tuple) and len(group) >= 2:
            images = group[0]
            err = group[1]
            debug = group[2] if len(group) >= 3 else {}
        else:
            images = tuple()
            err = 'invalid_group'
            debug = {}

        safe_kw = (keywords or '').strip()
        safe_kw_quoted = ', '.join([f'"{k.strip()}"' for k in safe_kw.split(',') if k.strip()])
        if not safe_kw_quoted:
            safe_kw_quoted = f'"{safe_kw}"' if safe_kw else '""'

        # Debug comment with request URL(s) + parameters
        debug_payload = {
            'provider': (debug or {}).get('provider', ''),
            'requests': (debug or {}).get('requests', []),
            'params': (debug or {}).get('params', {}),
        }
        debug_json = _safe_html_comment_text(json.dumps(debug_payload, ensure_ascii=False))

        # Each [i] block is a bordered "card" and will be centered by the images pane.
        html_lines.append(
            f'<div style="display:inline-block; text-align:center; margin: 0 auto 10px auto; '
            f'padding: 8px; border: 1px solid #eee; border-radius: 6px;">'
        )
        html_lines.append(f'{indent}<!-- image_search_request: {debug_json} -->')
        html_lines.append(f'{indent}<div style="margin: 2px 0 6px 0; font-size: 0.95em; color: #444;">')
        html_lines.append(f'{indent}{indent}<span style="font-weight: bold;">[{i}]</span>')
        html_lines.append(f'{indent}{indent}<span style="color:#666;">{safe_kw_quoted}</span>')
        html_lines.append(f'{indent}</div>')

        if not images:
            title = tr("Sem imagens") if 'tr' in globals() else 'Sem imagens'
            tooltip = err or 'no_results'
            html_lines.append(
                f'{indent}<div title="{tooltip}" style="font-size: 0.9em; color: #888; padding: 3px 0 8px 0;">{title}</div>'
            )
            html_lines.append(f'{indent}<!-- image_search_error: {_safe_html_comment_text(err or "no_results")} -->')
            html_lines.append('</div>')
            continue

        for (thumb_url, landing_url) in images:
            alt_text = _format_alt_text_for_keywords(keywords)
            link_url = _media_fragment_url(landing_url)

            img_style = 'display:block; width:100%; height:auto; border: 1px solid #ddd; border-radius: 3px;'
            if target_image_width_px:
                img_style = (
                    f'display:block; width:{int(target_image_width_px)}px; max-width:100%; height:auto; '
                    f'border: 1px solid #ddd; border-radius: 3px;'
                )

            html_lines.append(f'{indent}<a href="{link_url}" style="display:block; text-decoration:none; margin: 0 0 8px 0;">')
            html_lines.append(f'{indent}{indent}<div style="border: 1px solid #e5e5e5; border-radius: 4px; padding: 4px;">')
            html_lines.append(
                f'{indent}{indent}{indent}<img src="{thumb_url}" alt="{alt_text}" data-processed="true" style="{img_style}" />'
            )
            html_lines.append(f'{indent}{indent}</div>')
            html_lines.append(f'{indent}</a>')

        html_lines.append('</div>')

    return '\n'.join(html_lines)

