from playwright.sync_api import sync_playwright
import sys

def test_e2e():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        
        # Test 1: Price cards load
        page.goto('http://localhost:18000', wait_until='load')
        page.wait_for_selector('#card-XAUUSD', state='visible', timeout=20000)
        price = page.text_content('#price-XAUUSD')
        print(f'✅ Price card: {price}')
        
        # Test 2: Chart visible
        page.wait_for_selector('#priceChart', state='visible', timeout=10000)
        print('✅ Chart visible')
        
        b.close()
