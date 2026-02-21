import re

def parse_arn(soup):
    arn_tag = soup.find('font', string='Assessment Roll Number')
    if arn_tag:
        arn_text = arn_tag.find_next_sibling(text=True).strip()
        return re.sub(r'\D', '', arn_text)
    return ''
