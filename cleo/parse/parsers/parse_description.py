import re
from bs4 import BeautifulSoup, NavigableString, Tag

DEBUG = False

def debug_print(msg, level=0, tag=None):
    if DEBUG:
        indent = "  " * level
        tag_info = ""
        if tag:
            if isinstance(tag, Tag):
                tag_info = f" [Tag: {tag.name}]"
            elif isinstance(tag, NavigableString):
                tag_info = " [NavigableString]"
            tag_info += f" {repr(str(tag))[:100]}"
        print(f"{indent}DEBUG: {msg}{tag_info}")

def get_text_content(element):
    """Extract clean text content from an element"""
    if isinstance(element, NavigableString):
        text = str(element).strip()
        return text if text else None
    elif isinstance(element, Tag):
        if element.name == 'br':
            return '\n'
        elif element.name == 'a' and 'pdf' in element.get_text().lower():
            return f"more info: {element.get_text().strip()}"
        elif element.name == 'font' and element.get('color') == '#848484':
            return None  # Skip section headers
        elif element.name == 'p':
            return '\n\n'  # Double newline for paragraphs
        else:
            text = element.get_text().strip()
            return text if text else None
    return None

def parse_description(soup):
    """
    Extracts text between Description and Site sections.
    Uses a simpler approach of finding all text nodes between the tags.
    """
    debug_print("Starting parse_description")
    
    # Find the Description and Site tags
    description_tag = soup.find('font', {'color': '#848484'}, string=re.compile(r'Description', re.I))
    if not description_tag:
        debug_print("No Description tag found - returning empty string", 1)
        return ""
        
    site_tag = soup.find('font', {'color': '#848484'}, string=re.compile(r'Site', re.I))
    if not site_tag:
        debug_print("No Site tag found - returning empty string", 1)
        return ""

    debug_print("Found Description tag:", 1, description_tag)
    debug_print("Found Site tag:", 1, site_tag)

    # Get all elements between Description and Site tags
    current = description_tag.next_element
    text_blocks = []
    seen = set()
    last_was_newline = True  # Track if last added item was a newline
    
    while current and current != site_tag:
        debug_print(f"Processing element:", 1, current)
        
        # Get text content if any
        text = get_text_content(current)
        
        # Skip the Description header text
        if text == 'Description':
            current = current.next_element
            continue
            
        if text:
            # Handle newlines
            if text == '\n' or text == '\n\n':
                if not last_was_newline:
                    text_blocks.append('\n')
                    last_was_newline = True
            else:
                # Add non-newline text if not seen before
                clean_text = text.strip()
                if clean_text and clean_text not in seen and not clean_text.startswith('Site'):
                    if not last_was_newline and text_blocks:
                        text_blocks.append(' ')  # Add space between adjacent text
                    text_blocks.append(clean_text)
                    seen.add(clean_text)
                    last_was_newline = False
            
        # Move to next element
        current = current.next_element
        if not current:
            break

    # Join all text blocks
    text = ''.join(text_blocks)
    
    # Clean up the text
    # 1. Replace multiple newlines with double newlines
    text = re.sub(r'\n\s*\n\s*\n*', '\n\n', text)
    # 2. Remove leading/trailing whitespace
    text = text.strip()
    # 3. Remove any "Site" section content
    if ' Site ' in text:
        text = text.split(' Site ')[0].strip()
    # 4. Ensure only one "more info: mi.pdf"
    if 'more info: mi.pdf' in text:
        parts = text.split('more info:')
        text = parts[0].strip() + '\n\nmore info: mi.pdf'
    # 5. Fix any remaining formatting issues
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)  # Single newlines become spaces
    text = re.sub(r'\n\n+', '\n\n', text)  # Multiple newlines become double newlines
    text = text.strip()

    debug_print(f"Final result: {repr(text)}", 1)
    return text
