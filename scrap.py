from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
import requests
import json
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
}
response = requests.get("https://news.uestc.edu.cn/?n=UestcNews.Front.CategoryV2.Page&CatId=42", headers=headers)
print(response.status_code)
html_1 = response.text
soup = BeautifulSoup(html_1, 'html.parser')
items = soup.find_all("div", class_="item")
type(items)
news = []
for item in items:
    title_a = item.find("a", {"class":"title"})
    if title_a is None:
        continue
    href = title_a.get("href")
    if not href:
        continue
    query = parse_qs(urlparse(href).query)
    news_id = query["id"][0] if "id" in query else href
    date_div = item.find("div",{"class":"date"})
    content_div = item.find("div",{"class":"content"})
    news_date = date_div.get_text().strip() if date_div else ""
    news_title = title_a.get_text().strip()
    news_content = content_div.get_text().strip() if content_div else ""
    news.append(
        {
            "news_id": news_id,
            "news_date": news_date,
            "news_title": news_title,
            "news_content": news_content,
        }
    )

with open("news.json", "w", encoding="utf-8") as f:
    json.dump(news, f)



