# Theo - AI Team Builder

Build multi-agent teams through conversation with Theo.

## Quick Start

```bash
# Install dependencies
pip install -r theo/requirements.txt

# Set API key
export OPENAI_API_KEY='your-key-here'
or
set OPENAI_API_KEY in .env file

# Run from geodesic-ai root directory
python -m theo.main
```

## CLI Navigation

- **[key]** - Type the key in brackets to select an option
- **[b]** - Go back to previous menu
- **[q]** - Quit application
- **[?]** - Show help
- **Ctrl+C** - Cancel current operation

## Usage

1. **Create Project** - Set up a workspace for your teams
2. **Build New Team** - Talk to Theo about your problem
   - Theo discovers your intent
   - Theo designs the right team (conductor + specialists)
   - Team saved to `teams/` directory
3. **Explore Teams** - View teams, agents, and design rationale

## Requirements

- Python 3.8+
- OpenAI API key (set `OPENAI_API_KEY` environment variable)

## What You Get

Each team includes:
- `agents/` - YAML agent definitions (Geodesic-compatible)
- `composition.yaml` - Team structure
- `intent_package.json` - Original intent and context
- `theo_definition.json` - Full team design and report

## Project Structure

```
data/projects/{project_id}/
  info.json                  # Project metadata
  workflows/                 # Team workflows
    {workflow_id}.json       # References team in teams/

teams/{team_name}/           # Generated teams
  agents/                    # Agent YAML files
  composition.yaml           # Team composition
  intent_package.json        # Original intent
  theo_definition.json       # Full design + report
```
