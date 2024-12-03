import httpx

async def test_proxy(proxy_url):
    try:
        async with httpx.AsyncClient(proxies=proxy_url) as client:
            response = await client.get('https://api.ipify.org?format=json')
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Пример использования
import asyncio
proxy_url = "socks5://aNTAw2:TdLdgc@141.98.171.247:8000"
asyncio.run(test_proxy(proxy_url))