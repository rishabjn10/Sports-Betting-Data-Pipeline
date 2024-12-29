# Sports Betting Data Pipeline

A Python-based data pipeline that extracts sports betting data and syncs it to Google Sheets.

## Overview

This project automates the collection and processing of sports betting data, storing it in Google Sheets for further analysis. It includes features for event tracking, odds monitoring, and automated data synchronization.

## Prerequisites

- Python 3.8 or higher
- PDM (Python Development Master) package manager
- Google Cloud Platform account with Sheets API enabled
- Valid Google OAuth 2.0 credentials

## Installation

1. Clone the repository:

cd <project-directory>
cd src

2. Install dependencies:

pdm install

3. Set up Google Sheets credentials:
   - Create a project in Google Cloud Console
   - Enable Google Sheets API
   - Create OAuth 2.0 credentials
   - Download the credentials JSON file and save as `credentials.json` in the project root

## Configuration

1. Create a `.env` file in the project root:

SPREADSHEET_ID=your_spreadsheet_id
SERVICE_ACCOUNT_FILE=your_service_account_file_name e.g. credentials.json


## Development

### Setting up the development environment

1. Install development dependencies:
pdm install -d

2. Run the development server:
pdm run python .\main.py