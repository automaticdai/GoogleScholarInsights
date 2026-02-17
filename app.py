"""Flask web application for Google Scholar dashboard."""
import os
import json
import re
from flask import Flask, render_template, jsonify, send_from_directory
from scripts.analyze_data import ScholarAnalyzer, load_data

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Path to author data
AUTHOR_DATA_PATH = os.path.join(os.path.dirname(__file__), 'author_data.json')


@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')


@app.route('/api/data')
def get_author_data():
    """API endpoint to get author data."""
    try:
        data = load_data(AUTHOR_DATA_PATH)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Author data file not found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in author data file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analysis')
def get_analysis():
    """API endpoint to get analyzed author statistics."""
    try:
        data = load_data(AUTHOR_DATA_PATH)
        analyzer = ScholarAnalyzer(data)
        
        analysis = {
            'name': analyzer.name,
            'affiliation': data.get('affiliation', 'Unknown'),
            'email_domain': data.get('email_domain', ''),
            'homepage': data.get('homepage', ''),
            'url_picture': data.get('url_picture', ''),
            'interests': data.get('interests', []),
            'citation_metrics': analyzer.get_citation_metrics(),
            'research_areas': [{'term': term, 'count': count} 
                             for term, count in analyzer.get_research_areas(15)],
            'authorship_stats': analyzer.get_authorship_stats(),
            'publication_ranks': analyzer.get_publication_ranks(),
            'h_index': data.get('hindex', 0),
            'h_index_5y': data.get('hindex5y', 0),
            'i10_index': data.get('i10index', 0),
            'i10_index_5y': data.get('i10index5y', 0),
            'total_citations': data.get('citedby', 0),
            'total_citations_5y': data.get('citedby5y', 0),
            'total_publications': len(analyzer.publications),
            'publications': []
        }
        
        # Add publication summaries (top 20 for display)
        for pub in analyzer.publications[:20]:
            bib = pub.get('bib', {})
            venue = bib.get('venue') or bib.get('journal') or bib.get('conference') or ''
            if not venue:
                # Extract venue from citation string (format: "Venue, pages, year")
                citation = bib.get('citation', '')
                if citation:
                    venue = re.sub(r',\s*\d{4}\s*$', '', citation)
                    venue = re.sub(r',\s*[\d\u2013-]+\s*$', '', venue)
                    venue = re.sub(r'[\s\u2026.]*$', '', venue)
                    venue = re.sub(r'\s+(?:and|of|the|in|on|for|with|a|an)\s*$', '', venue, flags=re.IGNORECASE).strip()
            analysis['publications'].append({
                'title': bib.get('title', 'Unknown'),
                'year': bib.get('pub_year', 'Unknown'),
                'venue': venue,
                'citations': pub.get('num_citations', 0),
                'url': pub.get('pub_url', ''),
                'authors': bib.get('author', '')
            })
        
        return jsonify(analysis)
    except FileNotFoundError:
        return jsonify({'error': 'Author data file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

