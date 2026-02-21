import re
import traceback
from datetime import datetime

def format_price(price_str):
    try:
        # Remove any existing formatting
        price = ''.join(filter(str.isdigit, price_str))
        # Format with $ and commas
        return f"${int(price):,}"
    except:
        return ""

def normalize_sale_date(date_str):
    try:
        raw = date_str.strip()
        if not raw:
            return "", ""

        # Attempt multiple known patterns
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%d %b %Y"), dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Fallback: remove ordinal suffixes then retry
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw)
        dt = datetime.strptime(cleaned, "%d %b %Y")
        return dt.strftime("%d %b %Y"), dt.strftime("%Y-%m-%d")
    except Exception:
        return "", ""

def parse_sale_date_and_price(soup):
    try:
        result = {'SaleDate': '', 'SaleDateISO': '', 'SalePrice': ''}
        
        # Find the address tag
        address_tag = soup.find('strong', id='address')
        if not address_tag:
            print("DEBUG: No address tag found")
            return result
            
        # Find the city line by looking for text containing ': '
        current = address_tag
        while current:
            if isinstance(current, str) and ': ' in current:
                break
            current = current.next_sibling
            
        if not current:
            print("DEBUG: No city line found")
            return result
            
        # Get the next text node after the city line's <br>
        next_br = None
        node = current
        while node:
            if node.name == 'br':
                next_br = node
                break
            node = node.next_sibling
            
        if not next_br:
            print("DEBUG: No br after city line")
            return result
            
        # Get the sale details text
        sale_text = None
        node = next_br.next_sibling
        while node:
            if isinstance(node, str) and node.strip():
                sale_text = node.strip()
                break
            node = node.next_sibling
            
        if not sale_text:
            print("DEBUG: No sale text found")
            return result
            
        # Clean and parse the text
        if '$' not in sale_text:
            print("DEBUG: No $ in sale text")
            return result
            
        # Split on $ and handle the parts
        parts = sale_text.split('$')
        if len(parts) >= 2:
            date_part = parts[0].strip()
            price_part = parts[1].split()[0].strip() if parts[1] else ''
            
            if date_part:
                display_date, iso_date = normalize_sale_date(date_part)
                result['SaleDate'] = display_date
                result['SaleDateISO'] = iso_date
            if price_part:
                result['SalePrice'] = f"${price_part}"
                
        return result
        
    except Exception as e:
        print(f"Error parsing sale details: {str(e)}")
        traceback.print_exc()
        return {'SaleDate': '', 'SalePrice': ''}
