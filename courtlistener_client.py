"""
CourtListener API Client for Supreme Court Cases

This client fetches Supreme Court cases with opinions, concurrences, and dissents.
You'll need to create a free account at https://www.courtlistener.com/ to get an API token.
"""

import requests
import json
import time
from typing import Dict, List, Optional
from datetime import datetime


class CourtListenerClient:
    def __init__(self, api_token: str):
        """
        Initialize the CourtListener API client.
        
        Args:
            api_token: Your API token from CourtListener profile
        """
        self.base_url = "https://www.courtlistener.com/api/rest/v4"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        })
    
    def get_scotus_clusters(self, year: int, page_size: int = 100) -> List[Dict]:
        """
        Get all Supreme Court opinion clusters for a given year.
        
        Args:
            year: Year to fetch cases from
            page_size: Number of results per page (max 100)
        
        Returns:
            List of opinion cluster dictionaries
        """
        clusters = []
        url = f"{self.base_url}/clusters/"
        
        params = {
            'court': 'scotus',
            'date_filed__gte': f'{year}-05-01',
            'date_filed__lte': f'{year}-12-31',
            'page_size': page_size,
            'order_by': 'date_filed'
        }
        
        while url:
            print(f"Fetching: {url}")
            response = self.session.get(url, params=params if url == f"{self.base_url}/clusters/" else None)
            response.raise_for_status()
            
            data = response.json()
            clusters.extend(data['results'])
            
            url = data.get('next')
            params = None  # Only use params on first request
            
            # Be respectful of rate limits
            time.sleep(0.1)
        
        print(f"Found {len(clusters)} cases for {year}")
        return clusters
    
    def get_cluster_details(self, cluster_id: int) -> Dict:
        """
        Get detailed information about a specific opinion cluster.
        
        Args:
            cluster_id: The cluster ID
        
        Returns:
            Detailed cluster dictionary
        """
        url = f"{self.base_url}/clusters/{cluster_id}/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_opinions_for_cluster(self, cluster_id: int) -> List[Dict]:
        """
        Get all opinions (majority, concurrence, dissent) for a cluster.
        
        Args:
            cluster_id: The cluster ID
        
        Returns:
            List of opinion dictionaries with full text
        """
        url = f"{self.base_url}/opinions/"
        params = {
            'cluster': cluster_id,
            'page_size': 20
        }
        
        opinions = []
        while url:
            response = self.session.get(url, params=params if opinions == [] else None)
            response.raise_for_status()
            
            data = response.json()
            opinions.extend(data['results'])
            url = data.get('next')
            params = None
            
            time.sleep(0.1)
        
        return opinions
    
    def get_complete_case(self, cluster_id: int) -> Dict:
        """
        Get complete case information including all opinions.
        
        Args:
            cluster_id: The cluster ID
        
        Returns:
            Dictionary with case metadata and all opinions
        """
        cluster = self.get_cluster_details(cluster_id)
        opinions = self.get_opinions_for_cluster(cluster_id)
        
        return {
            'cluster': cluster,
            'opinions': opinions
        }
    
    def extract_case_data(self, cluster: Dict, opinions: List[Dict]) -> Dict:
        """
        Extract and structure the key data from a case.
        
        Args:
            cluster: Cluster dictionary
            opinions: List of opinion dictionaries
        
        Returns:
            Structured case data
        """
        case_data = {
            'case_name': cluster.get('case_name'),
            'case_name_short': cluster.get('case_name_short'),
            'docket_number': cluster.get('docket_number'),
            'date_filed': cluster.get('date_filed'),
            'date_argued': cluster.get('date_argued'),
            'citations': cluster.get('citations', []),
            'syllabus': cluster.get('syllabus'),
            'judges': cluster.get('judges'),
            'per_curiam': cluster.get('per_curiam'),
            'cluster_id': cluster.get('id'),
            'absolute_url': f"https://www.courtlistener.com{cluster.get('absolute_url', '')}",
            'opinions': []
        }
        
        # Process each opinion
        for opinion in opinions:
            opinion_data = {
                'type': opinion.get('type'),  # 010 = Majority, 020 = Concurrence, 030 = Dissent
                'type_label': self._get_opinion_type_label(opinion.get('type')),
                'author': opinion.get('author_str'),
                'author_id': opinion.get('author'),
                'joined_by': opinion.get('joined_by_str'),
                'plain_text': opinion.get('plain_text'),
                'html': opinion.get('html'),
                'html_with_citations': opinion.get('html_with_citations'),
                'extracted_by_ocr': opinion.get('extracted_by_ocr'),
                'opinion_id': opinion.get('id')
            }
            case_data['opinions'].append(opinion_data)
        
        return case_data
    
    def _get_opinion_type_label(self, type_code: str) -> str:
        """Convert opinion type code to label."""
        type_map = {
            '010': 'Opinion of the Court',
            '015': 'Opinion Relating to Orders',
            '020': 'Concurring Opinion',
            '025': 'Concurrence in Part',
            '030': 'Dissenting Opinion',
            '035': 'Dissent in Part',
            '040': 'Concur/Dissent',
            '050': 'Remittitur'
        }
        return type_map.get(type_code, f'Unknown ({type_code})')
    
    def fetch_year(self, year: int, save_to_file: bool = True, 
                   filename: Optional[str] = None) -> List[Dict]:
        """
        Fetch all Supreme Court cases for a given year with complete data.
        
        Args:
            year: Year to fetch
            save_to_file: Whether to save results to JSON file
            filename: Output filename (default: scotus_{year}_cases.json)
        
        Returns:
            List of structured case dictionaries
        """
        print(f"Fetching Supreme Court cases for {year}...")
        
        # Get all clusters for the year
        clusters = self.get_scotus_clusters(year)
        
        all_cases = []
        for i, cluster in enumerate(clusters, 1):
            cluster_id = cluster['id']
            print(f"Processing case {i}/{len(clusters)}: {cluster.get('case_name_short', 'Unknown')} (ID: {cluster_id})")
            
            try:
                # Get full cluster details and opinions
                full_cluster = self.get_cluster_details(cluster_id)
                opinions = self.get_opinions_for_cluster(cluster_id)
                
                # Structure the data
                case_data = self.extract_case_data(full_cluster, opinions)
                all_cases.append(case_data)
                
                # Be respectful of rate limits (5000/hour = ~1.4/second)
                time.sleep(0.8)
                
            except Exception as e:
                print(f"Error processing case {cluster_id}: {e}")
                continue
        
        if save_to_file:
            if filename is None:
                filename = f'scotus_{year}_cases.json'
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_cases, f, indent=2, ensure_ascii=False)
            
            print(f"\nSaved {len(all_cases)} cases to {filename}")
        
        return all_cases
    
    def get_opinion_stats(self, cases: List[Dict]) -> Dict:
        """
        Get statistics about the opinions in a set of cases.
        
        Args:
            cases: List of case dictionaries
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_cases': len(cases),
            'total_opinions': 0,
            'opinion_types': {},
            'cases_with_dissents': 0,
            'cases_with_concurrences': 0,
            'unanimous_cases': 0
        }
        
        for case in cases:
            opinions = case.get('opinions', [])
            stats['total_opinions'] += len(opinions)
            
            has_dissent = False
            has_concurrence = False
            
            for opinion in opinions:
                type_label = opinion.get('type_label', 'Unknown')
                stats['opinion_types'][type_label] = stats['opinion_types'].get(type_label, 0) + 1
                
                if 'Dissent' in type_label:
                    has_dissent = True
                elif 'Concur' in type_label:
                    has_concurrence = True
            
            if has_dissent:
                stats['cases_with_dissents'] += 1
            if has_concurrence:
                stats['cases_with_concurrences'] += 1
            if not has_dissent and not has_concurrence and len(opinions) == 1:
                stats['unanimous_cases'] += 1
        
        return stats


# Example usage
if __name__ == "__main__":
    # Get your API token from: https://www.courtlistener.com/profile/
    API_TOKEN = "dfe6a4ffb28480d2281e3a3894ab8045705e5a88"
    
    # Initialize client
    client = CourtListenerClient(API_TOKEN)
    
    # Fetch all 2025 Supreme Court cases
    cases = client.fetch_year(2025)
    
    # Get statistics
    stats = client.get_opinion_stats(cases)
    print("\nStatistics:")
    print(json.dumps(stats, indent=2))
    
    # Example: Access a specific case
    if cases:
        first_case = cases[0]
        print(f"\nFirst case: {first_case['case_name']}")
        print(f"Date filed: {first_case['date_filed']}")
        print(f"Number of opinions: {len(first_case['opinions'])}")
        
        for opinion in first_case['opinions']:
            print(f"  - {opinion['type_label']} by {opinion['author']}")
