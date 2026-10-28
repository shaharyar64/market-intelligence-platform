## Price Scraper

Internal scraper for scraping data from multiple social media platforms and other platforms like Instagram, Twitter, TikTok, Reddit and Google Trends. 



- platform : mention the ecommerce platform, from where the data is sourced 
- brand : name of brand like Amstel, Heineken 
- type : Type of beer, like lager or strong 
- quantity : In CL, like 33CL, 50CL 
- units : Number of pieces: 1, 4, 6, 12, 24 
- pack_format : Glass or Can 
- original_price_local : Price in AED/BAH in absolute terms like 49 AED 
- original_price_usd : Absolute Price converted in USD by using standard multiplier 0.272 USD for AED and 2.648 USD for BAH 
- discounted_price_local : Price in AED/BAH in absolute terms like 49 AED 
- currency : Like AED, or BHD
- discounted_price_usd : Absolute Price converted in USD by using standard multiplier 0.272 USD for AED and 2.648 USD for BAH 
- discount_percentage : % of discount (original price-discounted price)/Original Price x100 
- link : The actual link that takes you to the detailed 
- image_link : The link that takes you to the image of the product 
- availablility : Simple yes or no: the default across websites is available unless specified as Out of Stock 
- features_in_top10 : If the listing is amongst to 10, have this marked as yes, else no 
- features_on_first_page : If the listing is on the first page, have this marked as yes, else no




curl 'https://api2.citydrinks.com/catalog/v1/client/categories/beer-18/products?warehouseCode=DSKEZ&page%5Bsize%5D=48&page%5Bcurrent%5D=1&sort%5B0%5D%5Bfield%5D=salesQuantity&sort%5B0%5D%5Border%5D=DESC' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: en-US,en;q=0.8' \
  -H 'if-none-match: W/"281b2-ARCllEmhjG+/fKIkkJaM0plBWLg"' \
  -H 'origin: https://citydrinks.com' \
  -H 'priority: u=1, i' \
  -H 'referer: https://citydrinks.com/' \
  -H 'sec-ch-ua: "Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  -H 'sec-gpc: 1' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36' \
  -H 'x-company-id: 1eb53a13-5f9e-4deb-92d7-090a4b53fd21' \
  -H 'x-lang: en'



  