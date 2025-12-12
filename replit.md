# Lever Analyzer

## Overview
A Python/Streamlit application that integrates with Lever ATS to analyze and rank job candidates using AI-powered resume analysis.

## Features
- **Position Selection**: Searchable dropdown with all open and closed Lever positions
- **Weighted Requirements**: Define custom requirements with percentage weights for scoring
- **Optional Job Description**: Add custom job description for additional scoring criteria
- **Scoring Balance**: Slider to adjust weight between job description vs requirements
- **AI Analysis**: Uses OpenAI GPT-4o to analyze resumes and generate scores
- **Ranked Results**: Candidates displayed in descending order by score with:
  - Overall score with color indicators
  - Strengths and weaknesses
  - Direct link to Lever profile
  - LinkedIn link (when available)
  - Email address

## Project Structure
```
├── app.py              # Main Streamlit application
├── lever_client.py     # Lever API client for fetching positions/candidates/resumes
├── resume_analyzer.py  # OpenAI integration for resume analysis
├── .streamlit/
│   └── config.toml     # Streamlit server configuration
```

## Required Secrets
- `LEVER_API_KEY` - Your Lever API key (from Lever Settings > Integrations > API Credentials)
- `OPENAI_API_KEY` - Your OpenAI API key (for resume analysis)

## Running the App
```
streamlit run app.py --server.port 5000
```

## Technical Details
- **Lever API**: Uses Basic Auth with API key, fetches postings with mode=all to include closed positions
- **PDF Parsing**: Uses pdfplumber to extract text from resume PDFs
- **Concurrent Processing**: Analyzes multiple candidates in parallel (max 2 workers)
- **Rate Limiting**: Automatic retry with exponential backoff for API rate limits

## Recent Changes
- December 2024: Initial implementation with Lever integration and OpenAI analysis
