import requests
import xml.etree.ElementTree as ET
import csv
import re
import argparse
from typing import List, Dict, Optional

# PubMed API Base URLs
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Keywords to detect non-academic institutions
COMPANY_KEYWORDS = ["pharma", "biotech", "laboratories", "inc", "ltd", "corp", "gmbh", "s.a.", "co.", "llc"]

def fetch_pubmed_ids(query: str, max_results: int = 10) -> List[str]:
    """Fetch PubMed IDs matching the query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
    response = requests.get(PUBMED_SEARCH_URL, params=params)
    response.raise_for_status()
    data = response.json()
    
    return data.get("esearchresult", {}).get("idlist", [])

def fetch_pubmed_details(pubmed_ids: List[str]) -> List[Dict[str, str]]:
    """Fetch details for given PubMed IDs."""
    params = {
        "db": "pubmed",
        "id": ",".join(pubmed_ids),
        "retmode": "xml"
    }
    response = requests.get(PUBMED_FETCH_URL, params=params)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    papers = []
    
    for article in root.findall(".//PubmedArticle"):
        pubmed_id = article.find(".//PMID").text
        title = article.find(".//ArticleTitle").text
        pub_date = article.find(".//PubDate/Year")
        pub_date = pub_date.text if pub_date is not None else "Unknown"

        # Extract authors and affiliations
        non_academic_authors = []
        company_affiliations = []
        corresponding_email = None

        for author in article.findall(".//Author"):
            lastname = author.find("LastName")
            firstname = author.find("ForeName")
            name = f"{firstname.text} {lastname.text}" if firstname is not None and lastname is not None else "Unknown"

            affiliation = author.find(".//Affiliation")
            if affiliation is not None:
                affiliation_text = affiliation.text.lower()
                if any(keyword in affiliation_text for keyword in COMPANY_KEYWORDS):
                    non_academic_authors.append(name)
                    company_affiliations.append(affiliation.text)
            
            # Check for email in affiliation
            email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", affiliation.text if affiliation is not None else "")
            if email_match and corresponding_email is None:
                corresponding_email = email_match.group(0)

        if non_academic_authors:
            papers.append({
                "PubmedID": pubmed_id,
                "Title": title,
                "Publication Date": pub_date,
                "Non-academic Author(s)": "; ".join(non_academic_authors),
                "Company Affiliation(s)": "; ".join(set(company_affiliations)),
                "Corresponding Author Email": corresponding_email or "N/A"
            })

    return papers

def save_to_csv(papers: List[Dict[str, str]], filename: str = "pubmed_results.csv") -> None:
    """Save paper details to a CSV file."""
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["PubmedID", "Title", "Publication Date", "Non-academic Author(s)", "Company Affiliation(s)", "Corresponding Author Email"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for paper in papers:
            writer.writerow(paper)

def main():
    """Command-line interface for fetching PubMed papers."""
    parser = argparse.ArgumentParser(description="Fetch and filter PubMed research papers with non-academic authors.")
    parser.add_argument("query", type=str, help="PubMed search query")
    parser.add_argument("--max_results", type=int, default=10, help="Maximum number of papers to fetch")
    parser.add_argument("--output", type=str, default="pubmed_results.csv", help="Output CSV file name")
    
    args = parser.parse_args()

    print(f"Fetching PubMed papers for query: {args.query}")
    pubmed_ids = fetch_pubmed_ids(args.query, args.max_results)
    
    if not pubmed_ids:
        print("No results found.")
        return

    print(f"Found {len(pubmed_ids)} papers. Fetching details...")
    papers = fetch_pubmed_details(pubmed_ids)

    if papers:
        save_to_csv(papers, args.output)
        print(f"Results saved to {args.output}")
    else:
        print("No papers with non-academic authors found.")

if __name__ == "__main__":
    main()
