import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import io
import argparse

def get_default_dates():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    return start_date, end_date

def convert_date_format(date_str):
    """Convert YYYYMMDD to DD-MM-YYYY format required by NSE API"""
    date_obj = datetime.strptime(date_str, '%Y%m%d')
    return date_obj.strftime('%d-%m-%Y')

def clean_csv_headers(content):
    # Read CSV content into pandas DataFrame
    df = pd.read_csv(io.BytesIO(content))
    
    # Clean column names
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # Write to string buffer
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode('utf-8')

def get_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }

def get_api_headers(base_url):
    headers = get_headers()
    headers.update({
        'Accept': 'text/csv,application/x-csv,application/csv,text/x-csv,application/x-json,text/plain',
        'Referer': base_url,
        'X-Requested-With': 'XMLHttpRequest'
    })
    return headers

def download_data(session, base_url, api_endpoint, start_date_str, end_date_str, index='equities'):
    try:
        # Get cookies first with a timeout
        print(f"Fetching initial page to get cookies...")
        response = session.get(base_url, headers=get_headers(), timeout=10)
        response.raise_for_status()
        print(f"Initial page status code: {response.status_code}")
        
        # Prepare API request
        api_url = f"https://www.nseindia.com/api/{api_endpoint}?index={index}&from_date={start_date_str}&to_date={end_date_str}&csv=true"
        
        print(f"Downloading data from {start_date_str} to {end_date_str}...")
        print(f"API URL: {api_url}")
        response = session.get(api_url, headers=get_api_headers(base_url), timeout=30)
        print(f"API response status code: {response.status_code}")
        response.raise_for_status()
        
        if response.content:
            # Clean the CSV headers
            cleaned_content = clean_csv_headers(response.content)
            
            filename = f"{api_endpoint.replace('/', '_')}_{start_date_str}_{end_date_str}.csv"
            with open(filename, 'wb') as f:
                f.write(cleaned_content)
            print(f"CSV downloaded successfully for {start_date_str} to {end_date_str}.")
        else:
            print(f"No data received for {start_date_str} to {end_date_str}.")
            
    except requests.exceptions.Timeout:
        print(f"Request timed out for {start_date_str} to {end_date_str}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading CSV for {start_date_str} to {end_date_str}: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response content: {e.response.text[:500]}...")  # Print first 500 chars of error response

def download_all_data(start_date_str, end_date_str):
    session = get_session()
    try:
        # Define all endpoints and their base URLs
        endpoints = [
            {
                'base_url': 'https://www.nseindia.com/companies-listing/corporate-filings-announcements',
                'api_endpoint': 'corporate-announcements'
            },
            {
                'base_url': 'https://www.nseindia.com/companies-listing/corporate-filings-event-calendar',
                'api_endpoint': 'event-calendar'
            },
            {
                'base_url': 'https://www.nseindia.com/companies-listing/corporate-filings-actions',
                'api_endpoint': 'corporates-corporateActions'
            },
            {
                'base_url': 'https://www.nseindia.com/companies-listing/corporate-filings-financial-results',
                'api_endpoint': 'corporates-financial-results'
            }
        ]
        
        for endpoint in endpoints:
            print(f"\nDownloading data for {endpoint['api_endpoint']}...")
            download_data(session, endpoint['base_url'], endpoint['api_endpoint'], start_date_str, end_date_str)
            
    finally:
        session.close()

def main():
    # Get default dates
    default_start, default_end = get_default_dates()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download NSE data for a specified date range')
    parser.add_argument('--start_date', type=str, 
                      default=default_start.strftime('%Y%m%d'),
                      help='Start date in YYYYMMDD format (default: 5 days ago)')
    parser.add_argument('--end_date', type=str,
                      default=default_end.strftime('%Y%m%d'),
                      help='End date in YYYYMMDD format (default: today)')
    
    args = parser.parse_args()
    
    try:
        # Parse and validate dates
        overall_from_date = datetime.strptime(args.start_date, '%Y%m%d')
        overall_to_date = datetime.strptime(args.end_date, '%Y%m%d')
        
        if overall_from_date > overall_to_date:
            raise ValueError("Start date must be before or equal to end date")
            
        current_month_start = overall_from_date
        while current_month_start <= overall_to_date:
            current_month_end = current_month_start + relativedelta(months=1) - timedelta(days=1)
            if current_month_end > overall_to_date:
                current_month_end = overall_to_date
            if current_month_start < overall_from_date:
                current_month_start = overall_from_date
            
            # Convert dates to NSE API format (DD-MM-YYYY)
            start_date_str = current_month_start.strftime('%d-%m-%Y')
            end_date_str = current_month_end.strftime('%d-%m-%Y')
            
            print(f"\nProcessing date range: {args.start_date} to {args.end_date}")
            download_all_data(start_date_str, end_date_str)
            current_month_start += relativedelta(months=1)
            
    except ValueError as e:
        print(f"Error: {str(e)}")
        print("Please provide dates in YYYYMMDD format")
        exit(1)

if __name__ == "__main__":
    main()
