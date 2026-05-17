import asyncio
import re
from urllib.parse import quote

import aiohttp


async def main() -> None:
    q = "Grand Theft Auto V"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ru"}
    out: list[str] = []
    async with aiohttp.ClientSession(headers=headers, trust_env=True) as s:
        for url in [
            f"https://kupikod.com/shop?q={quote(q)}",
            "https://kupikod.com/shop/catalog",
            f"https://ggsel.net/catalog?search={quote(q)}",
            f"https://plati.market/search/{quote(q)}",
        ]:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                    t = await r.text(errors="ignore")
                    out.append(f"{url} -> {r.status} final={r.url} len={len(t)}")
                    links = re.findall(r'href="(/shop/[a-z0-9-]+)"', t)[:3]
                    if links:
                        out.append(f"  kupikod links: {links}")
                    links2 = re.findall(r'href="(https://ggsel\.net/[^"]+)"', t)[:3]
                    if links2:
                        out.append(f"  ggsel: {links2}")
                    prices = re.findall(r"(\d[\d\s]{2,7})\s*₽", t)[:5]
                    if prices:
                        out.append(f"  prices: {prices}")
            except Exception as e:
                out.append(f"{url} ERR {e}")
    path = r"C:\Users\mizzz\gameprice-watcher\probe_out.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    asyncio.run(main())
