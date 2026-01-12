#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import urllib.request
from urllib.parse import urljoin, urlparse


DOMAIN = "https://www.bronxvillefamilydental.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    # WordPress pages are UTF-8
    return raw.decode("utf-8", errors="replace")


def strip_noise(html: str) -> str:
    # WP Rocket/IE helper scripts
    html = re.sub(r"<script>if\(navigator\.userAgent\.match\(/MSIE.*?</script>", "", html, flags=re.I | re.S)
    html = re.sub(r"<script>\(\(\)=>\{class RocketLazyLoadScripts.*?</script>", "", html, flags=re.I | re.S)

    # Analytics blocks
    html = re.sub(r"<!-- Google Tag Manager -->.*?<!-- End Google Tag Manager -->", "", html, flags=re.I | re.S)
    html = re.sub(
        r"<!-- Google Tag Manager \(noscript\) -->.*?<!-- End Google Tag Manager \(noscript\) -->",
        "",
        html,
        flags=re.I | re.S,
    )
    html = re.sub(r"<!-- Meta Pixel Code -->.*?<!-- End Meta Pixel Code -->", "", html, flags=re.I | re.S)

    # UserWay widget
    html = re.sub(r"<script[^>]+cdn\.userway\.org/widget\.js[^>]*></script>", "", html, flags=re.I | re.S)

    # CleanTalk (external + inline config)
    html = re.sub(r"<script[^>]+cleantalk[^>]*></script>", "", html, flags=re.I | re.S)
    html = re.sub(r"<script[^>]+apbct-public-bundle_full-protection[^>]*></script>", "", html, flags=re.I | re.S)
    html = re.sub(r"<script[^>]*>\s*var\s+ctPublicFunctions\b.*?</script>", "", html, flags=re.I | re.S)
    html = re.sub(r"<script[^>]*>\s*var\s+ctPublic\s*=\s*\{.*?</script>", "", html, flags=re.I | re.S)

    # Convert rocket-delayed script tags into normal script tags
    html = re.sub(r'\btype="rocketlazyloadscript"\b', "", html, flags=re.I)
    html = re.sub(r"\sdata-rocket-src=", " src=", html, flags=re.I)
    html = re.sub(r'\sdata-rocket-[a-zA-Z0-9_-]+="[^"]*"', "", html)
    html = re.sub(r'\sdata-minify="[^"]*"', "", html)
    html = re.sub(r'\sdata-wp-strategy="[^"]*"', "", html)

    return html


def rewrite_asset_urls(html: str) -> str:
    # Rewrite CSS url(/...) -> url(https://domain/...) for assets
    def css_url_repl(m: re.Match[str]) -> str:
        prefix = m.group(1)  # url( or url(' or url("
        return f"{prefix}{DOMAIN}/"

    html = re.sub(r"url\((['\"]?)/", css_url_repl, html)

    # Rewrite common asset attributes that start with /wp-... or icons to absolute
    for attr in ("href", "src"):
        html = re.sub(
            rf'({attr}=")/(wp-(?:content|includes)/)',
            rf'\1{DOMAIN}/\2',
            html,
            flags=re.I,
        )
        html = re.sub(
            rf'({attr}=")/(apple-touch-icon\.png|favicon-[^"]+\.png|site\.webmanifest)',
            rf'\1{DOMAIN}/\2',
            html,
            flags=re.I,
        )

    # lazyload attributes
    html = re.sub(r'(data-lazy-src=")/(wp-(?:content|includes)/)', rf'\1{DOMAIN}/\2', html, flags=re.I)
    html = re.sub(r'(data-rocket-src=")/(wp-(?:content|includes)/)', rf'\1{DOMAIN}/\2', html, flags=re.I)

    # srcset-like attributes
    html = re.sub(r'(srcset=")/(wp-(?:content|includes)/)', rf'\1{DOMAIN}/\2', html, flags=re.I)
    html = re.sub(r'(data-lazy-srcset=")/(wp-(?:content|includes)/)', rf'\1{DOMAIN}/\2', html, flags=re.I)

    return html


def inject_shim(html: str) -> str:
    shim = """
<script>
(function(){
  function delazify(){
    document.querySelectorAll('img[data-lazy-src]').forEach(function(img){
      var lazy = img.getAttribute('data-lazy-src');
      if(!lazy) return;
      var cur = img.getAttribute('src') || '';
      if(!cur || cur.indexOf('data:image') === 0) img.setAttribute('src', lazy);
      img.removeAttribute('data-lazy-src');
    });
    document.querySelectorAll('source[data-lazy-srcset]').forEach(function(source){
      var lazy = source.getAttribute('data-lazy-srcset');
      if(!lazy) return;
      source.setAttribute('srcset', lazy);
      source.removeAttribute('data-lazy-srcset');
    });
  }

  function setupNav(){
    var opener = document.querySelector('.menu-opener');
    if(opener){
      opener.addEventListener('click', function(e){
        e.preventDefault();
        document.body.classList.toggle('nav-open');
      });
    }
    document.querySelectorAll('#nav .opener').forEach(function(span){
      span.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var li = span.closest('li');
        if(li) li.classList.toggle('open');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    delazify();
    setupNav();
  });
})();
</script>
""".strip()
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", shim + "\n</body>", html, flags=re.I, count=1)
    return html + "\n" + shim


def output_path_for_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == "/":
        return "/workspace/index.html"
    # Ensure directory-style output
    if not path.endswith("/"):
        path = path + "/"
    return os.path.join("/workspace", path.lstrip("/"), "index.html")


def write_page(out_path: str, html: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def main() -> int:
    pages = [
        "/",
        "/about-us/",
        "/our-services/",
        "/new-patients/",
        "/contact-us/",
        "/about-us/meet-our-doctors/",
        "/about-us/meet-our-team/",
        "/new-patients/patient-reviews/",
        "/new-patients/dental-membership-plan/",
        "/our-services/invisalign/",
    ]

    for path in pages:
        url = urljoin(DOMAIN, path)
        print(f"Fetching {url} ...", file=sys.stderr)
        html = fetch(url)
        html = strip_noise(html)
        # Remove any <base> tag from upstream; we want local navigation
        html = re.sub(r"<base\b[^>]*>", "", html, flags=re.I)
        html = rewrite_asset_urls(html)
        html = inject_shim(html)

        out_path = output_path_for_url(url)
        write_page(out_path, html)
        print(f"Wrote {out_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

